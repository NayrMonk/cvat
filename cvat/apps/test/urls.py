# SPDX-License-Identifier: MIT

from django.urls import path

from . import views

urlpatterns = [
    path(
        "annotation-stats/tasks/<int:task_id>",
        views.TaskAnnotationCountsView.as_view(),
        name="annotation_stats_task",
    ),
]
