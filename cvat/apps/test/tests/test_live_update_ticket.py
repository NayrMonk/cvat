# SPDX-License-Identifier: MIT

import time
from http import HTTPStatus
from unittest import mock

from django.test import SimpleTestCase

from cvat.apps.engine.models import Task
from cvat.apps.engine.tests.utils import ApiTestBase, ForceLogin
from cvat.apps.iam.models import User
from cvat.apps.test.tickets import TICKET_MAX_AGE_SECONDS, issue_ticket, ticket_allows


class TicketRulesTest(SimpleTestCase):
    def test_ticket_opens_only_the_task_it_was_issued_for(self):
        ticket = issue_ticket(task_id=7)

        self.assertTrue(ticket_allows(ticket, 7))
        self.assertFalse(ticket_allows(ticket, 8))

    def test_tampered_or_empty_ticket_is_refused(self):
        ticket = issue_ticket(task_id=7)

        self.assertFalse(ticket_allows(ticket[:-2] + "xx", 7))
        self.assertFalse(ticket_allows("", 7))
        self.assertFalse(ticket_allows("not-a-ticket", 7))

    def test_expired_ticket_is_refused(self):
        ticket = issue_ticket(task_id=7)

        later = time.time() + TICKET_MAX_AGE_SECONDS + 1
        with mock.patch("django.core.signing.time.time", return_value=later):
            self.assertFalse(ticket_allows(ticket, 7))


class LiveUpdateTicketEndpointTest(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="owner", password="owner")
        self.outsider = User.objects.create_user(username="outsider", password="outsider")
        self.task = Task.objects.create(name="live task", owner=self.owner)

    def _get(self, task_id: int, user: User | None):
        with ForceLogin(user, self.client):
            return self.client.get(f"/api/annotation-stats/tasks/{task_id}/ticket")

    def test_user_with_access_gets_a_ticket_for_that_task(self):
        response = self._get(self.task.id, self.owner)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        ticket = response.json()["ticket"]
        self.assertTrue(ticket_allows(ticket, self.task.id))
        self.assertFalse(ticket_allows(ticket, self.task.id + 1))

    def test_request_without_login_gets_no_ticket(self):
        self.assertEqual(self._get(self.task.id, None).status_code, HTTPStatus.UNAUTHORIZED)

    def test_user_without_access_gets_no_ticket(self):
        self.assertEqual(self._get(self.task.id, self.outsider).status_code, HTTPStatus.FORBIDDEN)

    def test_unknown_task_gets_no_ticket(self):
        response = self._get(self.task.id + 1000, self.owner)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
