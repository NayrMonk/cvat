# SPDX-License-Identifier: MIT

from django.apps import AppConfig


class AnnotationStatsConfig(AppConfig):
    name = "cvat.apps.test"
    verbose_name = "Annotation statistics"

    def ready(self) -> None:
        from . import signals  # pylint: disable=unused-import
