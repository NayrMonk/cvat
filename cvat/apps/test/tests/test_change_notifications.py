# SPDX-License-Identifier: MIT

from unittest import mock

import redis
from django.test import TestCase

from cvat.apps.engine.models import Task
from cvat.apps.iam.models import User
from cvat.apps.test import signals
from cvat.apps.test.pubsub import channel_for


class TaskChangeNotificationTest(TestCase):
    def setUp(self):
        owner = User.objects.create_user(username="owner", password="owner")
        self.task = Task.objects.create(name="watched task", owner=owner)

    def test_touching_a_task_announces_its_change_once_committed(self):
        with mock.patch.object(signals, "publish_task_changed") as publish:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.task.touch()

            publish.assert_not_called()  # nothing is sent before the transaction commits
            self.assertEqual(len(callbacks), 1)

            callbacks[0]()
            publish.assert_called_once_with(self.task.id)

    def test_other_saves_of_a_task_are_not_announced(self):
        with mock.patch.object(signals, "publish_task_changed") as publish:
            with self.captureOnCommitCallbacks(execute=True):
                self.task.name = "renamed"
                self.task.save()
                self.task.save(update_fields=["name"])

            publish.assert_not_called()

    def test_publishing_uses_a_channel_per_task(self):
        self.assertNotEqual(channel_for(1), channel_for(2))
        self.assertIn("1", channel_for(1))

    def test_a_redis_outage_does_not_break_the_caller(self):
        with mock.patch.object(signals, "_publisher") as publisher:
            publisher.return_value.publish.side_effect = redis.ConnectionError("redis is down")

            with self.assertLogs(signals.logger, level="WARNING"):
                signals.publish_task_changed(self.task.id)  # must not raise
