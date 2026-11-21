# Plan — Annotation Analytics for CVAT

Branch `dev-test01`, forked from `cvat-ai/cvat` `develop` at `d4d08dedb5ad7c5e980c0bc7319a7f5587365dad`.
Budget: 8 hours of work. Docker builds and the COCO import run in the background and are not counted.

## Goal

For one task, show how many annotations exist per class: an API that counts in the database, and a page in
CVAT's UI that draws the counts as a bar chart, updated live.

## What I found before writing code

- An annotation's class is the `label` foreign key on CVAT's abstract `Annotation` model
  (`cvat/apps/engine/models.py`). It is inherited by `LabeledShape`, `LabeledTrack`, `LabeledImage` (tags) and,
  in this CVAT version, `LabeledInterval` (audio). Annotations belong to a `Job`. A job belongs to a `Segment`, and a segment belongs to a `Task`.
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

Decided before starting: project-level and job-level dashboards, counts over time, server-side caching (only if MO-1
is missed), UI unit tests.

Decided later, after an independent review of the finished code (each also appears in "Not finished" in the
Definition of Done):
- **Overlapping jobs.** An object on a frame two jobs share is stored once per job and counts twice. Fixing it needs
  CVAT's geometric matching; giving each frame to one job instead would hide real work. Pinned by a test.
- **Deleted frames.** Annotations on a deleted frame still count, because CVAT keeps them until the frame is restored.
- **Project-level label edits** are not pushed live: they touch the project, not its tasks. The page catches up on
  the next change or reconnect.
- **The ticket** appears in the access log for the 60 seconds it is valid, and is not single-use.
- **`cvat/schema.yml`** is not regenerated: the assessment does not ask for it, it is a large generated file, and the
  pull request goes into my own fork rather than upstream.

## Dataset

COCO 2017 val: all 5000 images, `instances_val2017.json` imported as COCO 1.0.

## Changes to this plan

I did not keep a clock per step, so the time column above is the estimate I started with, not a record of what each
step took. What did change, and why:

1. **Order of items 2–5.** My first draft put auth before the page. The assessment says to work down its list in
   order, so the page, graph and error states came first (commit `011d6987`).
2. **Chart.js directly, not `react-chartjs-2`.** The quality-control chart in CVAT already uses Chart.js on a canvas;
   a second way of drawing charts would be one more thing to learn.
3. **How the stack was started.** The assessment says `docker compose up -d`, which pulls CVAT's prebuilt images. They
   do not contain the new app or page, so the images were built from the fork with `docker-compose.dev.yml`. For
   iteration a local-only override mounted the working tree's backend code into the containers; it is excluded from
   git and not part of the submission.
4. **MO-1 is measured with the session cookie, not Basic auth.** A pilot showed Basic auth costs about 240 ms per request,
   almost all of it Django hashing the password, so it would have timed the password check instead of the endpoint.
5. **MO-2 is measured by a script, not by console marks read by hand.** Same interval, repeatable.
6. **Socket authentication uses a signed ticket, not the session cookie.** See the decision record.
7. **Added after the independent review:** audio intervals are counted; sockets close after ten minutes so access is
   re-checked; a failed live refresh now shows a "may be out of date" warning instead of a green badge; a test goes
   through CVAT's real save path to the announcement.
8. **Bugs I found in my own work while testing**, all fixed with the reason in the commit message: the heartbeat sent a
   spurious `ping` on every connection (`2a2fcb70`); a failed refresh could leave the page on its spinner with no
   Retry button (`4230bb6c`); malformed socket requests could raise before any check (`94bc9d95`).

## Decision record

**The question.** How does the open page find out that annotations changed?

**Taken.** A notification, not data. A `post_save` receiver on `Task` fires on `Task.touch()`, which every annotation
write ends in, and publishes `changed` on a per-task channel of the Redis CVAT already runs. A small raw ASGI handler
(`cvat/apps/test/websocket.py`, wired in `cvat/asgi.py`) forwards it to the page over a WebSocket, and the page
refetches the counts over REST. The socket is opened with a short-lived signed ticket that the REST side issues only
to users who may view the task.

**Rejected: Django Channels.** It is the standard answer: consumers, groups, an auth middleware and a test client.

What rejecting it cost:
- About a hundred lines I own and had to get right. My own tests found two real bugs in them (a spurious heartbeat on
  every connection, and unhandled malformed input), and the review found a third gap (a socket outliving the user's
  access). Channels would have handled none of the product-specific parts, but it would have handled the ASGI
  plumbing I wrote by hand.
- No group abstraction and no Channels test client, so the tests drive the handler with a small fake socket.
- Authentication: Channels would authenticate from the session cookie in its middleware. I could not do that cheaply
  (see below), which led to the ticket and its own costs.

What it bought: no new dependency, so no image rebuild, no new moving part to run, and the feature rides on the
`uvicorn`, `websockets` and `redis` packages the server image already ships.

**Rejected: authenticating the socket from the session cookie.** It would need CVAT's permission engine and
organization context inside code that has no request object, and would be open to cross-site WebSocket hijacking unless
`Origin` were checked too. What the ticket costs: one more endpoint, one extra request each time the page connects (which
also re-checks the session), a ticket that is visible in the access log for its 60 seconds, and a socket that is only
re-checked when it is renewed (every ten minutes) rather than continuously.

**Rejected: sending the new counts over the socket.** It would save a round trip. It would also create a second path
that has to enforce access to the task, and a way for the chart to show numbers the user may no longer be allowed to
see. The cost is one REST request (about 50 ms) after every notification, and about 300 ms of deliberate delay so that
a burst of saves causes one refetch.

**Rejected: a maintained counter table instead of `GROUP BY` on demand.** It would make the read constant-time. It
would also have to hook every write path (UI save, import, delete, label change, job reassignment) and could drift from
the truth. The cost is that the query grows with the number of annotations: 52.8 ms for 41,866 is comfortable, but
nothing here has been measured at millions of rows and an index review would then be needed.
