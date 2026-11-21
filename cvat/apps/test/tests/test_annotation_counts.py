# SPDX-License-Identifier: MIT

from http import HTTPStatus

from cvat.apps.engine.models import (
    Job,
    JobType,
    Label,
    LabeledImage,
    LabeledShape,
    LabeledTrack,
    Segment,
    Task,
)
from cvat.apps.engine.tests.utils import ApiTestBase, ForceLogin
from cvat.apps.iam.models import User


class TaskAnnotationCountsTest(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="owner", password="owner")
        self.outsider = User.objects.create_user(username="outsider", password="outsider")

        self.task = Task.objects.create(name="counted task", owner=self.owner)
        self.cat = Label.objects.create(task=self.task, name="cat")
        self.dog = Label.objects.create(task=self.task, name="dog")
        self.bird = Label.objects.create(task=self.task, name="bird")
        self.job = self._add_job(JobType.ANNOTATION)

    def _add_job(self, job_type: JobType) -> Job:
        segment = Segment.objects.create(task=self.task, start_frame=0, stop_frame=9)
        return Job.objects.create(segment=segment, type=job_type)

    def _add_shapes(
        self, job: Job, label: Label, amount: int, shape_type: str = "rectangle", **extra
    ) -> list[LabeledShape]:
        return [
            LabeledShape.objects.create(job=job, label=label, frame=i, type=shape_type, **extra)
            for i in range(amount)
        ]

    def _get(self, task_id: int, user: User | None):
        with ForceLogin(user, self.client):
            return self.client.get(f"/api/annotation-stats/tasks/{task_id}")

    def _counts(self, response) -> dict[str, int]:
        return {label["name"]: label["count"] for label in response.json()["labels"]}

    def test_counts_shapes_tracks_and_tags_per_label(self):
        self._add_shapes(self.job, self.cat, 3)
        LabeledTrack.objects.create(job=self.job, label=self.cat, frame=0)
        LabeledImage.objects.create(job=self.job, label=self.dog, frame=0)

        response = self._get(self.task.id, self.owner)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(self._counts(response), {"cat": 4, "dog": 1, "bird": 0})
        self.assertEqual(response.json()["total"], 5)

    def test_labels_are_sorted_by_count_and_include_zero_counts(self):
        self._add_shapes(self.job, self.dog, 2)
        self._add_shapes(self.job, self.cat, 1)

        response = self._get(self.task.id, self.owner)

        names = [label["name"] for label in response.json()["labels"]]
        self.assertEqual(names, ["dog", "cat", "bird"])

    def test_task_without_annotations_has_zero_total(self):
        response = self._get(self.task.id, self.owner)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["total"], 0)
        self.assertEqual(len(response.json()["labels"]), 3)

    def test_skeleton_points_and_ground_truth_jobs_are_not_counted(self):
        skeleton = self._add_shapes(self.job, self.cat, 1, shape_type="skeleton")[0]
        self._add_shapes(self.job, self.cat, 2, parent=skeleton)
        self._add_shapes(self._add_job(JobType.GROUND_TRUTH), self.cat, 5)

        response = self._get(self.task.id, self.owner)

        self.assertEqual(self._counts(response)["cat"], 1)

    def test_other_tasks_are_not_counted(self):
        other = Task.objects.create(name="other", owner=self.owner)
        other_label = Label.objects.create(task=other, name="cat")
        other_job = Job.objects.create(
            segment=Segment.objects.create(task=other, start_frame=0, stop_frame=9)
        )
        self._add_shapes(other_job, other_label, 4)
        self._add_shapes(self.job, self.cat, 1)

        response = self._get(self.task.id, self.owner)

        self.assertEqual(response.json()["total"], 1)

    def test_request_without_login_is_refused(self):
        response = self._get(self.task.id, None)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_user_without_access_to_the_task_is_refused(self):
        response = self._get(self.task.id, self.outsider)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_unknown_task_is_not_found(self):
        response = self._get(self.task.id + 1000, self.owner)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
