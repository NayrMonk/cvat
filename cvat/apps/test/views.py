# SPDX-License-Identifier: MIT

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cvat.apps.engine.models import Task

from .serializers import TaskAnnotationCountsSerializer
from .services import count_annotations_by_label


class TaskAnnotationCountsView(APIView):
    # Replaces CVAT's default PolicyEnforcer, which requires a viewset-style iam_permission_class.
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["annotation-stats"],
        summary="Count a task's annotations per label",
        responses=TaskAnnotationCountsSerializer,
    )
    def get(self, request, task_id: int):
        task = get_object_or_404(Task, id=task_id)
        counts = count_annotations_by_label(task)
        return Response(TaskAnnotationCountsSerializer(counts).data)
