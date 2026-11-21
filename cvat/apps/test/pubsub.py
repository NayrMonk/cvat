# SPDX-License-Identifier: MIT

from django.conf import settings


def channel_for(task_id: int) -> str:
    return f"annotation-stats:task:{task_id}"


def redis_connection_kwargs() -> dict:
    # Same in-memory Redis that CVAT's job queues use, so no new service is needed.
    redis_settings = settings.REDIS_INMEM_SETTINGS
    return {
        "host": redis_settings["HOST"],
        "port": redis_settings["PORT"],
        "db": redis_settings["DB"],
        "password": redis_settings["PASSWORD"],
    }
