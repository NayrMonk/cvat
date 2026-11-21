# SPDX-License-Identifier: MIT

import asyncio
import json
from unittest import mock

import redis
from django.test import SimpleTestCase

from cvat.apps.test import signals, websocket
from cvat.apps.test.pubsub import channel_for
from cvat.apps.test.tickets import issue_ticket

TIMEOUT = 3


class FakeSocket:
    """The two ends of an ASGI WebSocket connection, driven by the test."""

    def __init__(self, task_id: int, ticket: str):
        self.scope = {
            "type": "websocket",
            "path": f"/api/annotation-stats/ws/tasks/{task_id}",
            "query_string": f"ticket={ticket}".encode(),
        }
        self.to_server = asyncio.Queue()
        self.from_server = asyncio.Queue()
        self.to_server.put_nowait({"type": "websocket.connect"})

    async def receive(self):
        return await self.to_server.get()

    async def send(self, message):
        await self.from_server.put(message)

    async def next_message(self, timeout: float = TIMEOUT) -> dict:
        return await asyncio.wait_for(self.from_server.get(), timeout)

    async def next_event(self, timeout: float = TIMEOUT) -> str:
        message = await self.next_message(timeout)
        assert message["type"] == "websocket.send", message
        return json.loads(message["text"])["type"]

    def disconnect(self):
        self.to_server.put_nowait({"type": "websocket.disconnect", "code": 1000})


def start(socket: FakeSocket) -> asyncio.Task:
    app = websocket.route_websockets(mock.AsyncMock())
    return asyncio.create_task(app(socket.scope, socket.receive, socket.send))


async def announce_when_subscribed(task_id: int) -> None:
    """Publishes until the handler has subscribed, which PUBLISH reports as a receiver count."""
    publisher = signals._publisher()
    for _ in range(100):
        if await asyncio.to_thread(publisher.publish, channel_for(task_id), "changed"):
            return
        await asyncio.sleep(0.05)
    raise AssertionError("the handler never subscribed to the task's channel")


class TicketCheckTest(SimpleTestCase):
    async def _closed_with(self, socket: FakeSocket) -> int:
        handler = start(socket)
        self.assertEqual((await socket.next_message())["type"], "websocket.accept")
        message = await socket.next_message()
        await asyncio.wait_for(handler, TIMEOUT)
        self.assertEqual(message["type"], "websocket.close")
        return message["code"]

    async def test_missing_ticket_is_closed_with_a_code_the_page_can_read(self):
        code = await self._closed_with(FakeSocket(5, ticket=""))

        self.assertEqual(code, websocket.CLOSE_TICKET_REJECTED)

    async def test_ticket_for_another_task_is_refused(self):
        code = await self._closed_with(FakeSocket(5, ticket=issue_ticket(task_id=6, user_id=1)))

        self.assertEqual(code, websocket.CLOSE_TICKET_REJECTED)

    async def test_forged_ticket_is_refused(self):
        code = await self._closed_with(FakeSocket(5, ticket="forged"))

        self.assertEqual(code, websocket.CLOSE_TICKET_REJECTED)

    async def test_query_string_that_is_not_utf8_is_refused_not_a_crash(self):
        socket = FakeSocket(5, ticket="")
        socket.scope["query_string"] = b"ticket=" + bytes([0xFF, 0xFE])  # not valid UTF-8

        self.assertEqual(await self._closed_with(socket), websocket.CLOSE_TICKET_REJECTED)


class LiveUpdatesTest(SimpleTestCase):
    async def _open(self, task_id: int = 5) -> tuple[FakeSocket, asyncio.Task]:
        socket = FakeSocket(task_id, issue_ticket(task_id, user_id=1))
        handler = start(socket)
        self.assertEqual((await socket.next_message())["type"], "websocket.accept")
        return socket, handler

    async def test_a_change_of_the_task_is_forwarded_to_the_page(self):
        socket, handler = await self._open()

        await announce_when_subscribed(5)

        self.assertEqual(await socket.next_event(), "changed")
        socket.disconnect()
        await asyncio.wait_for(handler, TIMEOUT)

    async def test_changes_of_other_tasks_are_not_forwarded(self):
        socket, handler = await self._open(5)
        await announce_when_subscribed(5)
        self.assertEqual(await socket.next_event(), "changed")

        await asyncio.to_thread(signals._publisher().publish, channel_for(6), "changed")

        with self.assertRaises(asyncio.TimeoutError):
            await socket.next_message(timeout=0.4)
        socket.disconnect()
        await asyncio.wait_for(handler, TIMEOUT)

    async def test_an_idle_socket_gets_a_heartbeat_only_once_the_interval_has_passed(self):
        interval = 0.4
        with mock.patch.object(websocket, "HEARTBEAT_SECONDS", interval):
            started = asyncio.get_running_loop().time()
            socket, handler = await self._open()

            self.assertEqual(await socket.next_event(), "ping")
            waited = asyncio.get_running_loop().time() - started

            self.assertGreaterEqual(waited, interval * 0.9)  # not sent early
            socket.disconnect()
            await asyncio.wait_for(handler, TIMEOUT)

    async def test_the_first_frame_is_not_a_spurious_heartbeat(self):
        socket, handler = await self._open()

        with self.assertRaises(asyncio.TimeoutError):
            await socket.next_message(timeout=0.5)
        socket.disconnect()
        await asyncio.wait_for(handler, TIMEOUT)

    async def test_disconnect_ends_the_handler_and_releases_its_subscription(self):
        socket, handler = await self._open()
        await announce_when_subscribed(5)

        socket.disconnect()
        await asyncio.wait_for(handler, TIMEOUT)

        # nobody is listening any more, so a publish reaches no one
        receivers = await asyncio.to_thread(signals._publisher().publish, channel_for(5), "x")
        self.assertEqual(receivers, 0)

    async def test_a_socket_is_closed_for_renewal_when_it_reaches_its_lifetime(self):
        with mock.patch.object(websocket, "SOCKET_MAX_AGE_SECONDS", 0.3):
            socket, handler = await self._open()

            message = await socket.next_message()
            await asyncio.wait_for(handler, TIMEOUT)

        self.assertEqual(message, {"type": "websocket.close", "code": websocket.CLOSE_RENEW})

    async def test_a_socket_that_is_still_young_is_left_open(self):
        socket, handler = await self._open()

        with self.assertRaises(asyncio.TimeoutError):
            await socket.next_message(timeout=0.5)
        self.assertFalse(handler.done())
        socket.disconnect()
        await asyncio.wait_for(handler, TIMEOUT)

    async def test_redis_failure_closes_the_socket_so_the_page_reconnects(self):
        class BrokenRedis:
            def pubsub(self):
                return self

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                return False

            async def subscribe(self, *channels):
                raise redis.ConnectionError("redis is down")

            async def aclose(self):
                pass

        with mock.patch.object(websocket.aioredis, "Redis", lambda **kwargs: BrokenRedis()):
            with self.assertLogs(websocket.logger, level="ERROR"):
                socket, handler = await self._open()
                message = await socket.next_message()
                await asyncio.wait_for(handler, TIMEOUT)

        self.assertEqual(
            message, {"type": "websocket.close", "code": websocket.CLOSE_SERVER_ERROR}
        )


class RoutingTest(SimpleTestCase):
    async def test_http_requests_go_to_the_wrapped_app(self):
        wrapped = mock.AsyncMock()
        scope, receive, send = {"type": "http", "path": "/api/server/about"}, object(), object()

        await websocket.route_websockets(wrapped)(scope, receive, send)

        wrapped.assert_awaited_once_with(scope, receive, send)

    async def test_unknown_websocket_path_is_refused(self):
        wrapped = mock.AsyncMock()
        socket = FakeSocket(5, "")
        socket.scope["path"] = "/api/something/else"

        await websocket.route_websockets(wrapped)(socket.scope, socket.receive, socket.send)

        # refused before it is accepted, which a client sees as an HTTP 403
        self.assertEqual(await socket.next_message(), {"type": "websocket.close"})
        wrapped.assert_not_awaited()

    async def test_task_id_too_long_to_be_real_is_refused_without_an_error(self):
        wrapped = mock.AsyncMock()
        socket = FakeSocket(5, "")
        socket.scope["path"] = "/api/annotation-stats/ws/tasks/" + "9" * 5000

        await websocket.route_websockets(wrapped)(socket.scope, socket.receive, socket.send)

        self.assertEqual(await socket.next_message(), {"type": "websocket.close"})
        wrapped.assert_not_awaited()
