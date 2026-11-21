# SPDX-License-Identifier: MIT

from django.core import signing

_SALT = "annotation-stats-live-updates"

# A ticket is only used to open a socket right after it is issued, so it can be short-lived.
TICKET_MAX_AGE_SECONDS = 60


def issue_ticket(task_id: int, user_id: int) -> str:
    return signing.dumps({"task": task_id, "user": user_id}, salt=_SALT)


def ticket_allows(ticket: str, task_id: int) -> bool:
    try:
        payload = signing.loads(ticket, salt=_SALT, max_age=TICKET_MAX_AGE_SECONDS)
    except signing.BadSignature:  # also covers an expired ticket
        return False

    return payload.get("task") == task_id
