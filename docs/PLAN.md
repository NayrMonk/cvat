# Plan — Annotation Analytics for CVAT

Branch `dev-test01`, forked from `cvat-ai/cvat` `develop` at `d4d08dedb5ad7c5e980c0bc7319a7f5587365dad`.
Budget: 8 hours of work. Docker builds and the COCO import run in the background and are not counted.

## Goal

For one task, show how many annotations exist per class: an API that counts in the database, and a page in
CVAT's UI that draws the counts as a bar chart, updated live.

## What I found before writing code

- An annotation's class is the `label` foreign key on CVAT's abstract `Annotation` model
  (`cvat/apps/engine/models.py`). It is inherited by `LabeledShape`, `LabeledTrack` and `LabeledImage` (tags).
  Annotations belong to a `Job`. A job belongs to a `Segment`, and a segment belongs to a `Task`.
- Skeleton parts are child shapes (`parent` set), and ground-truth and consensus jobs repeat frames.
  Counting them would inflate the numbers, so I count only top-level annotations in `annotation`-type jobs.
- Every annotation write ends in `JobAnnotation._set_updated_date()` (`cvat/apps/dataset_manager/task.py`),
  which calls `Task.touch()`. This happens for UI saves and for imports in RQ workers. It is the hook for
  live updates, and it needs no change to CVAT's own code.
- CVAT already runs uvicorn (ASGI) behind nginx, which forwards WebSocket upgrades. The server image already ships
  `websockets` and `redis`, and the UI already ships `chart.js`. I plan to add no new dependencies.

## Order of work and time

| # | Step | Time |
|---|------|------|
| 0 | This plan, Definition of Done, objective targets (this commit, no code) | 0:30 |
| 1 | Django app `test`: endpoint `GET /api/annotation-stats/tasks/<id>`, counts with `GROUP BY` in Postgres | 1:00 |
| 2–4 | UI page `/tasks/<id>/annotation-stats`: bar chart, loading, empty and error states with retry | 1:30 |
| 5 | Auth on the same endpoint: 401 without login, 403 via CVAT's `TaskPermission` "view" check; tests | 0:30 |
| 6 | Measure MO-1 (see Objectives), 5 runs, fix if missed | 0:45 |
| 7 | Split each bar by annotation source (file / manual / auto / semi-auto) | 0:30 |
| 8 | Live updates: `post_save` on `Task.touch()` → Redis publish → WebSocket → page refetches | 1:15 |
| 9 | Reconnect with backoff, refetch after reconnect, connection status on the page | 0:45 |
| 10 | Decision record, Definition of Done ticked with evidence | 0:30 |
| – | Buffer | 0:45 |

I work down the assessment's list in order. Items 1–4 are the floor: nothing after them starts until the page
handles the empty and failure cases.

**Why split by source (item 7):** a COCO task starts with everything imported (`file`). The split shows how much
of each class came from the import and how much people drew by hand (`manual`) or a model produced (`auto`). With
live updates, the manual part grows while you watch. It is one extra column in the same `GROUP BY`, so it costs
no extra query.

## Deliberately skipped

Project-level and job-level dashboards, counts over time, server-side caching (only if MO-1 is missed), UI unit tests.

## Dataset

COCO 2017 val: all 5000 images, `instances_val2017.json` imported as COCO 1.0.

## Changes to this plan

_(Recorded here as they happen, with the reason.)_

## Decision record

_(Written when item 10 is reached.)_
