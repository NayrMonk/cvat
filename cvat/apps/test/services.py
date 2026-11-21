# SPDX-License-Identifier: MIT

from collections import Counter

from django.db.models import Count

from cvat.apps.engine.models import (
    JobType,
    LabeledImage,
    LabeledInterval,
    LabeledShape,
    LabeledTrack,
    SourceType,
    Task,
)


def count_annotations_by_label(task: Task) -> dict:
    """
    Counts a task's annotations per label (class) with GROUP BY queries in the database.

    Shapes, tracks, tags and intervals (audio) are stored in separate tables, so each is grouped
    on its own, the results are summed per label, and they are split by where the annotation came
    from (imported from a file, drawn by hand, or produced by a model).

    An annotation here is one stored object. Only top-level objects in regular annotation jobs are
    counted: skeleton points are child rows (parent set) of one skeleton, and ground truth or
    replica jobs repeat frames that a regular job already covers.

    Consequences of counting what is stored, not what an export would contain:
    - an object on a frame that two overlapping jobs share is stored once per job, so it counts
      twice; CVAT itself only reconciles those with geometric matching when it merges jobs;
    - an object on a deleted frame still counts, because CVAT keeps it until the frame is restored.
    """
    in_task = {"job__segment__task_id": task.id, "job__type": JobType.ANNOTATION.value}

    querysets = (
        LabeledShape.objects.filter(**in_task, parent__isnull=True),
        LabeledTrack.objects.filter(**in_task, parent__isnull=True),
        LabeledImage.objects.filter(**in_task),
        LabeledInterval.objects.filter(**in_task),
    )

    counts = Counter()
    for queryset in querysets:
        for row in queryset.values("label_id", "source").annotate(count=Count("id")).order_by():
            # source is nullable; a missing value means the model default
            source = row["source"] or SourceType.MANUAL.value
            counts[row["label_id"], source] += row["count"]

    labels = []
    for label in task.get_labels().values("id", "name", "color"):
        by_source = {source.value: counts[label["id"], source.value] for source in SourceType}
        labels.append({**label, "count": sum(by_source.values()), "by_source": by_source})
    labels.sort(key=lambda label: (-label["count"], label["name"]))

    return {"task_id": task.id, "total": sum(label["count"] for label in labels), "labels": labels}
