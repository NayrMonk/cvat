# SPDX-License-Identifier: MIT

from collections import Counter

from django.db.models import Count

from cvat.apps.engine.models import (
    JobType,
    LabeledImage,
    LabeledShape,
    LabeledTrack,
    SourceType,
    Task,
)


def count_annotations_by_label(task: Task) -> dict:
    """
    Counts a task's annotations per label (class) with GROUP BY queries in the database.

    Shapes, tracks and tags are stored in separate tables, so each is grouped on its own and
    the results are summed per label, and split by where the annotation came from (imported
    from a file, drawn by hand, or produced by a model).

    Only top-level objects in regular annotation jobs are counted: skeleton points are child
    rows (parent set) of one skeleton, and ground truth or consensus replica jobs repeat frames
    that a regular job already covers.
    """
    in_task = {"job__segment__task_id": task.id, "job__type": JobType.ANNOTATION.value}

    querysets = (
        LabeledShape.objects.filter(**in_task, parent__isnull=True),
        LabeledTrack.objects.filter(**in_task, parent__isnull=True),
        LabeledImage.objects.filter(**in_task),
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
