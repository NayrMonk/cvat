# Definition of Done

Written before any code (commit `d2dced7f`) and ticked at the end. A line is ticked only with evidence beside it: a
number, raw output, a screenshot or a commit. A line that did not fully pass is not ticked, or says what is missing.
Screenshots are in `docs/evidence/`; the machine, CPU, RAM, OS and base commit are in `OBJECTIVES.md`.

**Setup behind the numbers.** COCO 2017 val, all 5,000 images, `instances_val2017.json` imported as COCO 1.0: 36,781
COCO annotations in 80 classes. The stack was built from this fork's source with `docker-compose.dev.yml`. Two users:
`admin` (superuser, owner of the task) and `outsider` (an ordinary user with no access to it).

## Floor (items 1–4)

- [x] **Endpoint totals per class match a count computed straight from `instances_val2017.json`.** 80 of 80 classes,
  41,866 = 41,866 (commit `d6bd8a12`):

  ```
  endpoint total=41866  coco total=41866  classes=80
  classes that differ: 0
  ```

  The first comparison did **not** match: the endpoint said 41,866 and the COCO file 36,781, with 77 of 80 classes
  different. The cause is how CVAT imports: each polygon part of a multi-part object becomes its own shape. 3,522
  COCO annotations have more than one part, which is 5,085 extra shapes, and 36,781 + 5,085 = 41,866. I worked that
  total out from the COCO file before looking at the database, and every per-class gap matched too (car +383,
  bench +144, airplane +17). So the endpoint counts what is stored, and an annotation here is one stored shape. The
  expected count per class, which is what the comparison above is made against:

  ```python
  for a in coco["annotations"]:
      seg = a["segmentation"]
      parts = len(seg) if isinstance(seg, list) and not a["iscrowd"] else 1   # a crowd region is one mask
      expected[names[a["category_id"]]] += parts
  ```
- [x] **Classes with no annotations still appear, and skeleton parts and ground-truth jobs are not counted.** Tests
  `test_task_without_annotations_has_zero_total`, `test_labels_are_sorted_by_count_and_include_zero_counts` and
  `test_skeleton_points_and_ground_truth_jobs_are_not_counted` (`c15d187d`). The empty task returned its two labels at 0
  (`page-empty-task.png`).
- [x] **The task page links to the stats page, and the page shows the counts as a bar chart.** In Chrome, the task's
  Actions menu lists "Annotations per class" next to "View analytics"; clicking it opened
  `/tasks/1/annotation-stats` with the chart drawn (`783c5dfa`; `page-live-update-stacked.png`):

  ```
  clicked "Annotations per class" -> http://localhost:8080/tasks/1/annotation-stats | chart drawn
  ```
- [x] **Empty task → a "no annotations yet" state, not an empty chart.** `page-empty-task.png` (`2611accd`).
- [x] **Failed request → an error with a Retry button that works.** `page-failed-request.png` (the stats request blocked
  in the browser) and `page-after-retry.png` (the chart back after one click). Errors with no point in retrying (403, 404,
  401) show no Retry button on purpose: `page-403-no-access.png`.

## Access (item 5)

Raw output on the final code (`b2ccc389`, unchanged since in behaviour):

```
$ curl -i http://localhost:8080/api/annotation-stats/tasks/1             # no login
HTTP/1.1 401 Unauthorized
{"detail":"Authentication credentials were not provided."}
$ curl -i -u outsider:*** .../tasks/1                                     # logged in, no access to task 1
HTTP/1.1 403 Forbidden
{"detail":"You do not have access to this task"}
$ curl -i -u admin:*** .../tasks/1                                        # task owner
HTTP/1.1 200 OK
{"task_id":1,"total":41866,"labels":[{"id":1,"name":"person","color":"#c06060","count":12451,"by_source":{...
$ curl -i -u admin:*** .../tasks/99999                                    # unknown task
HTTP/1.1 404 Not Found
```

- [x] No login → `401`.
- [x] A logged-in user with no access to the task → `403` (the same OPA "view task" rule CVAT's own task endpoints use).
- [x] The owner → `200` with the counts.
- [x] Backend tests for 200, 401, 403 and 404 pass: `test_request_without_login_is_refused`,
  `test_user_without_access_to_the_task_is_refused`, `test_unknown_task_is_not_found` and the 200 cases (`c15d187d`).
  Whole suite in one run: `Ran 42 tests … OK` (counts 13, announcements 4, tickets 7, sockets 15, save-path triggers 3).

## Speed (item 6)

- [x] **MO-1 measured:** 5 runs of 20 requests, raw output pasted in `OBJECTIVES.md`, median and spread reported.
  Final run on the submitted code: median **52.8 ms**, run medians 51.9 to 57.5 ms (`23e60258`).
- [x] **Target met:** the target (median ≤ 100 ms) was set before measuring and not moved. It was cleared with about
  47 ms to spare, so it was not a tight target; the doc says so. The number rose as the query grew (44.7, then 48.2,
  then 52.8 ms) and the cost of each step was not profiled. Basic auth, which costs about 240 ms, was not used and the
  doc says why.

## Beyond the floor (items 7–10)

- [x] **Bars are split by source, and the split equals the plain count.** Tests `test_counts_are_split_by_source`,
  `test_source_split_adds_up_to_the_plain_count`, `test_missing_source_counts_as_manual` (`db588aed`); on the real task
  the parts add up to the count for all 80 labels and all 41,866 are `file`. `page-live-update-stacked.png` shows
  imported, manual and automatic segments (`c62ccf37`). Limit: when imported boxes dominate, the other segments are a
  few pixels wide; the exact split is in the tooltip.
- [x] **Drawing a box in a job updates the graph in another window without a reload.** Drawn with the mouse in CVAT's
  annotation page in one Chrome window, Save pressed; the stats page in a second window, untouched, went 41,866 → 41,867
  (`annotation-page-box-drawn.png`, `page-after-drawing-in-annotation-page.png`):

  ```
  tab A (stats page) is Live with 41866 annotations
  tab B: rectangle drawn on the canvas, saving...
  tab A (never touched) now shows 41867 annotations, 758 ms after pressing Save in tab B
  removed again -> tab A shows 41866
  ```

  That 758 ms includes CVAT's own save round trip. Saves made through the REST call alone (MO-2, 5 runs): median
  **378 ms**, target 1 s, met (`23e60258`; `abfdbdcd`, `2a2fcb70`).
- [x] **After `docker restart cvat_server` the page shows "Reconnecting", then recovers with current counts.**
  `page-reconnecting.png`, `page-recovered-after-restart.png` (`4230bb6c`):

  ```
  A) docker restart cvat_server while the page stays open
    +1.0s badge=Reconnecting
    +77.3s badge=Live (recovered)
    after the restart a new save (HTTP 200) still reaches the page: total=41867
  B) drop only the socket, refuse reconnects, change the data meanwhile
    saved (HTTP 200) while disconnected; page still shows 41866 (it cannot know yet)
    connection allowed again -> Live and caught up to 41867 in 142 ms
  ```

  The 77 s is the restart (about 45 s) plus up to 30 s of retry wait, which is the backoff cap. A lower cap would
  recover sooner at the price of more retries from every open page. In B the page learnt of a change for which no
  message was ever delivered, because it refetches on every reconnection.
- [x] **A WebSocket without a login, or for a task the user cannot see, is refused.** A socket cannot be opened without
  a ticket, a ticket needs a login and access, and bad tickets are closed (`6016a3a0`, `2a2fcb70`, `94bc9d95`):

  ```
  ticket, no login          -> 401
  ticket, outsider          -> 403
  socket, no ticket         -> close 4401
  socket, forged ticket     -> close 4401
  socket, ticket of task 1 used on task 2 -> close 4401
  socket, unknown path      -> refused at handshake, HTTP 403
  socket, valid ticket      -> connected; "changed" received on save and on delete
  ```

  Access is checked when the ticket is issued and again every ten minutes, when the socket is renewed. A user whose
  access is revoked can therefore still receive content-free "changed" events for up to ten minutes (see below).
- [x] **Decision record written in the Plan:** `PLAN.md` (`f969ca7a`): what was taken, what was rejected, and what each
  rejection cost.

## Hygiene

- [x] **The plan was committed before any code, and commits are small with a why.** `d2dced7f` (docs only) is the
  first commit; the first code is `2e56394e`, four commits later. There are 29 commits, one per step, each saying what
  changed and why. The first three documentation commits were rebuilt from amended versions, and two later messages
  were corrected, all before they were first pushed; nothing was rewritten after a push.
- [x] **No dead code, commented-out blocks or stray files.** A scan of everything added found no TODO, debug print,
  commented-out code or stray file, and `git status` is clean. `docker-compose.override.yml`, a local-only file that
  mounts the backend for iteration, is excluded from git and is not part of the submission. Two small things I kept on
  purpose: the response still carries each label's `color` although the page now colours by source (useful to anyone
  drawing their own chart from the API), and a ticket carries only the task id.
- [x] **No new dependencies:** `git diff --stat d4d08ded..HEAD` over the requirements and `package.json` files is empty.
- [x] **Everything not finished is listed below.**

## Checked by an independent review, not only by me

Five reviewers, each with a different lens (security, async robustness, frontend state, tests and presentation, CVAT
integration), read the finished code; every finding was then put to skeptics whose job was to refute it. 14 findings
survived and 14 were refuted. The real ones were fixed and tested: audio intervals not counted (`a6a4b1c5`), a socket
outliving the user's access, and malformed socket requests raising errors (`94bc9d95`), stale numbers behind a "Live"
badge (`page-stale-warning.png`) and an unannounced status (`01733033`), no test through CVAT's real save path (`683ca0f4`; with the receiver
deliberately broken all three tests fail), and a ticket field that implied it was tied to the user (`8db1c88e`).

## Not finished, and why

- **`cvat/schema.yml` is not regenerated.** The assessment does not ask for it, it is a large generated file, and the
  pull request goes into my own fork. The endpoints are still described by `extend_schema` on the views.
- **Overlapping jobs count an object once per job.** Fixing it needs CVAT's geometric matching, and giving each frame
  to one job would hide real work. A test pins the current behaviour.
- **Annotations on deleted frames still count,** because CVAT keeps them until the frame is restored.
- **Edits to project-level labels are not pushed live,** since they touch the project and not its tasks. The page
  catches up on the next change or reconnection.
- **The ticket appears in the access log for its 60 seconds and is not single-use,** and a socket survives up to ten
  minutes after a user's access is revoked. What leaks is the timing of edits, never the counts.
- **Only one shape of data was measured:** one task, one job, 41,866 shapes, one open page. Overlapping segments and
  audio intervals are covered by unit tests but were not tried on real tasks, and nothing was measured at millions of rows.
- **No automated frontend tests are in the repository.** The page and the hook were verified with headless Chrome
  scripts that I kept out of the repository to keep the change contained, so the UI evidence here is the raw output and
  screenshots above, and cannot be re-run from the repo.
- **The chart has no table alternative for screen readers;** only the connection status is announced.
- **The page fetches the counts twice on open:** once for the initial load and once when the socket first connects.
  Each is about 50 ms, and the second is what lets a page that opened during an outage catch up.
- **I kept no clock per step,** so the time column in the Plan is the original estimate, not a record.
- **Outside the repository:** the Loom recording and the pull request into my own fork are submission steps, not files.
