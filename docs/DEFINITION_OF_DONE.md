# Definition of Done

Written before any code. Each line is ticked only with evidence beside it: a number, raw output, a screenshot or a
commit link. A tick without evidence counts as not done.

## Floor (items 1–4)

- [ ] Endpoint totals per class match a count computed straight from `instances_val2017.json` for the same images.
- [ ] Classes with zero annotations still appear (with 0) and skeleton parts / ground-truth jobs are not counted.
- [ ] The task page links to the stats page, and the page shows the counts as a bar chart.
- [ ] Empty task → the page shows a "no annotations yet" state, not an empty chart.
- [ ] Failed request (server stopped, unknown task) → the page shows an error with a Retry button that works.

## Access (item 5)

- [ ] No login → `401`, shown with raw `curl` output.
- [ ] Logged-in user with no access to the task → `403`, shown with raw `curl` output.
- [ ] Owner → `200` with the counts.
- [ ] Backend tests for 200 / 401 / 403 / 404 pass.

## Speed (item 6)

- [ ] MO-1 measured: 5 runs, raw output pasted in Objectives, median and spread reported.
- [ ] Target met, or missed with the reason written down.

## Beyond the floor (items 7–10)

- [ ] Bars are split by source, and the split totals equal the plain totals.
- [ ] Drawing a box in a job updates the graph in another tab without reloading.
- [ ] After `docker restart cvat_server` the page shows "reconnecting", then recovers and shows current counts.
- [ ] A WebSocket without login, or for a task I can't see, is refused.
- [ ] Decision record written in the Plan.

## Hygiene

- [ ] Plan committed first, before any code. Commits are small, and the messages say what changed and why.
- [ ] No dead code, no commented-out blocks, no stray files. No new dependencies.
- [ ] Everything I did not finish is listed below, with the reason.

## Not finished

_(Filled in at the end.)_
