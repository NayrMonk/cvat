# SPDX-License-Identifier: MIT

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cvat.apps.engine.models import Task
from cvat.apps.engine.permissions import TaskPermission

from .serializers import LiveUpdateTicketSerializer, TaskAnnotationCountsSerializer
from .services import count_annotations_by_label
from .tickets import issue_ticket


def get_viewable_task(request, task_id: int) -> Task:
    task = get_object_or_404(Task, id=task_id)
    if not TaskPermission.create_scope_view(request, task).check_access().allow:
        raise PermissionDenied("You do not have access to this task")

    return task


class TaskAnnotationCountsView(APIView):
    # Replaces CVAT's default PolicyEnforcer, which requires a viewset-style iam_permission_class.
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["annotation-stats"],
        summary="Count a task's annotations per label",
        responses=TaskAnnotationCountsSerializer,
    )
    def get(self, request, task_id: int):
        task = get_viewable_task(request, task_id)
        counts = count_annotations_by_label(task)
        return Response(TaskAnnotationCountsSerializer(counts).data)


class LiveUpdateTicketView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["annotation-stats"],
        summary="Get a short-lived ticket for opening the live-update WebSocket of a task",
        responses=LiveUpdateTicketSerializer,
    )
    def get(self, request, task_id: int):
        task = get_viewable_task(request, task_id)
        return Response({"ticket": issue_ticket(task.id, request.user.id)})
