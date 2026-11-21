# SPDX-License-Identifier: MIT

import asyncio
import contextlib
import json
import logging
import re
from urllib.parse import parse_qs

import redis.asyncio as aioredis

from .pubsub import channel_for, redis_connection_kwargs
from .tickets import ticket_allows

logger = logging.getLogger(__name__)

# At most 18 digits: a longer id cannot be a task id, and int() refuses very long digit strings.
SOCKET_PATH = re.compile(r"^/api/annotation-stats/ws/tasks/(?P<task_id>\d{1,18})$")

# The nginx inside the server container closes a proxied connection that has been idle for 60
# seconds (its default proxy_read_timeout), so an idle socket has to carry traffic more often.
HEARTBEAT_SECONDS = 25

# A ticket is checked once, when the socket opens, so without a limit a socket would outlive the
# user's access to the task (removed from the organization, unassigned, logged out). Closing after
# this long makes the page fetch a new ticket, which re-checks that access.
SOCKET_MAX_AGE_SECONDS = 600

CLOSE_SERVER_ERROR = 1011  # the page should reconnect
CLOSE_TICKET_REJECTED = 4401
CLOSE_RENEW = 4002  # lifetime reached: the page reconnects at once with a new ticket


async def _forward_changes(pubsub, send) -> None:
    loop = asyncio.get_running_loop()
    last_sent = loop.time()
    while True:
        remaining = max(0.0, HEARTBEAT_SECONDS - (loop.time() - last_sent))
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=remaining)

        # get_message also returns None when it only consumed Redis's own subscription
        # confirmation, so "no message" does not mean the interval has passed.
        if message is None and loop.time() - last_sent < HEARTBEAT_SECONDS:
            continue

        event = "changed" if message else "ping"
        await send({"type": "websocket.send", "text": json.dumps({"type": event})})
        last_sent = loop.time()


async def _wait_for_disconnect(receive) -> None:
    while (await receive())["type"] != "websocket.disconnect":
        pass


async def _serve_task_changes(task_id: int, receive, send) -> bool:
    """Serves the socket until the client leaves; returns True if it ran into its lifetime limit."""
    client = aioredis.Redis(**redis_connection_kwargs())
    try:
        async with client.pubsub() as pubsub:
            await pubsub.subscribe(channel_for(task_id))

            forwarder = asyncio.create_task(_forward_changes(pubsub, send))
            disconnected = asyncio.create_task(_wait_for_disconnect(receive))
            done, pending = await asyncio.wait(
                {forwarder, disconnected},
                timeout=SOCKET_MAX_AGE_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            if forwarder in done and disconnected not in done:
                forwarder.result()  # forwarding stopped on its own: surface why

            return not done
    finally:
        await client.aclose()


async def task_stats_socket(scope, receive, send, task_id: int) -> None:
    await receive()  # the websocket.connect event

    # The socket is accepted before the ticket is checked: a refusal before accept reaches the
    # browser as an anonymous network failure, while a close code can be told apart.
    await send({"type": "websocket.accept"})

    query = parse_qs(scope["query_string"].decode(errors="replace"))
    ticket = query.get("ticket", [""])[0]
    if not ticket_allows(ticket, task_id):
        await send({"type": "websocket.close", "code": CLOSE_TICKET_REJECTED})
        return

    try:
        if await _serve_task_changes(task_id, receive, send):
            await send({"type": "websocket.close", "code": CLOSE_RENEW})
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Live updates for task %s stopped", task_id)
        with contextlib.suppress(Exception):
            await send({"type": "websocket.close", "code": CLOSE_SERVER_ERROR})


def route_websockets(http_app):
    """Sends this feature's WebSocket paths to its handler and everything else to Django."""

    async def application(scope, receive, send):
        if scope["type"] != "websocket":
            await http_app(scope, receive, send)
            return

        match = SOCKET_PATH.match(scope["path"])
        if match is None:
            # Django's ASGI handler only speaks HTTP, so an unknown socket path is refused here.
            # Closing before accepting is an HTTP 403 for the client, whatever code is given.
            await receive()
            await send({"type": "websocket.close"})
            return

        await task_stats_socket(scope, receive, send, int(match["task_id"]))

    return application
