# SPDX-License-Identifier: MIT

import logging
from functools import lru_cache

import redis
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from cvat.apps.engine.models import Task

from .pubsub import channel_for, redis_connection_kwargs

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _publisher() -> redis.Redis:
    return redis.Redis(**redis_connection_kwargs())


def publish_task_changed(task_id: int) -> None:
    try:
        _publisher().publish(channel_for(task_id), "changed")
    except redis.RedisError:
        # A missed notification only delays the chart until the next one or a reconnect;
        # it must never make saving an annotation fail.
        logger.warning("Could not announce a change of task %s", task_id, exc_info=True)


@receiver(post_save, sender=Task)
def announce_task_change(sender, instance: Task, update_fields=None, **kwargs) -> None:
    # Every annotation write ends in Task.touch(), which saves only updated_date
    # (JobAnnotation._set_updated_date in dataset_manager/task.py). Listening for exactly that
    # save covers edits made in the UI and imports run by RQ workers alike, without touching
    # CVAT's own code. Other touches (e.g. label edits) also change the counts, so a refetch
    # on those is correct too.
    if update_fields != {"updated_date"}:
        return

    # Wait for the commit so a client that refetches immediately sees the new rows.
    transaction.on_commit(lambda: publish_task_changed(instance.id))
