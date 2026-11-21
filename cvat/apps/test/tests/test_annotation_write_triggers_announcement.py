# SPDX-License-Identifier: MIT

from unittest import mock

from django.test import TestCase

from cvat.apps.dataset_manager.task import PatchAction, patch_job_data, put_job_data
from cvat.apps.engine.models import Data, Job, Label, Segment, Task
from cvat.apps.iam.models import User
from cvat.apps.test import signals


class AnnotationWriteTriggersAnnouncementTest(TestCase):
    """The live updates rely on CVAT's own save path ending in Task.touch(); these tests go
    through that path, so they fail if a CVAT change stops it from touching the task."""

    def setUp(self):
        owner = User.objects.create_user(username="owner", password="owner")
        self.task = Task.objects.create(
            name="written task", owner=owner, data=Data.objects.create(size=10, image_quality=70)
        )
        self.label = Label.objects.create(task=self.task, name="cat")
        segment = Segment.objects.create(task=self.task, start_frame=0, stop_frame=9)
        self.job = Job.objects.create(segment=segment)

    def _shape(self, **extra) -> dict:
        return {
            "type": "rectangle", "frame": 0, "label_id": self.label.id, "points": [1, 1, 9, 9],
            "occluded": False, "outside": False, "z_order": 0, "rotation": 0, "group": 0,
            "source": "manual", "attributes": [], **extra,
        }

    def _data(self, *shapes: dict) -> dict:
        return {"shapes": list(shapes), "tracks": [], "tags": [], "intervals": []}

    def _announced_while(self, write) -> list:
        with mock.patch.object(signals, "publish_task_changed") as publish:
            with self.captureOnCommitCallbacks(execute=True):
                write()
        return publish.call_args_list

    def test_creating_an_annotation_announces_the_change(self):
        calls = self._announced_while(lambda: patch_job_data(
            self.job.id, self._data(self._shape()), PatchAction.CREATE
        ))

        self.assertEqual(calls, [mock.call(self.task.id)])

    def test_replacing_annotations_as_an_import_does_announces_the_change(self):
        calls = self._announced_while(lambda: put_job_data(
            self.job.id, self._data(self._shape())
        ))

        self.assertEqual(calls, [mock.call(self.task.id)])

    def test_deleting_an_annotation_announces_the_change(self):
        created = patch_job_data(
            self.job.id, self._data(self._shape()), PatchAction.CREATE
        )
        shape = {**self._shape(), "id": created["shapes"][0]["id"]}

        calls = self._announced_while(lambda: patch_job_data(
            self.job.id, self._data(shape), PatchAction.DELETE
        ))

        self.assertEqual(calls, [mock.call(self.task.id)])
