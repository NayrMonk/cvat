# Objectives

## Machine

| | |
|---|---|
| CPU | 12th Gen Intel Core i7-12700 (12 cores / 20 threads) |
| RAM | 15.7 GB |
| OS | Windows 11 Pro 10.0.26300, Docker Desktop (WSL 2 backend) |
| CVAT commit | `d4d08dedb5ad7c5e980c0bc7319a7f5587365dad` (`develop`, cloned before any change) |
| Data | COCO 2017 val, 5000 images, `instances_val2017.json` imported as COCO 1.0 |

## MO-1 — endpoint response time

| Field | Entry |
|---|---|
| What is measured | Total time for `GET /api/annotation-stats/tasks/<id>` on the 5000-image COCO task, as seen by the client. |
| How | `curl -s -o /dev/null -w "%{time_total}"` with Basic auth against `http://localhost:8080`. One warm-up request is discarded. A run is 20 sequential requests, and the run's value is their median. |
| Target | Median of 5 runs at or below **100 ms**. |
| Conditions | Local Docker stack, nothing else running, the same task each time, no other requests in flight. |
| Not included | The first request after a container start, browser rendering, WebSocket delivery. |

**Why 100 ms:** every live change makes the page fetch again, so the endpoint's cost repeats for every change, for
every open page. 100 ms keeps a live update looking immediate. It is also tight enough that permission checks plus
counting ~36.8k annotations across three tables could plausibly miss it.

**Result:** _(raw output, median and spread added after measuring.)_

## MO-2 — live update latency (stretch)

| Field | Entry |
|---|---|
| What is measured | Time from saving a new box in a job to the stats page in another tab showing the new count. |
| How | `performance.now()` logged in the browser console when the WebSocket message arrives and when the chart re-renders with new data, plus the save request's end time from the network panel. |
| Target | Median of 5 runs at or below **1 s**. |
| Conditions | Same as MO-1, two tabs in one Chrome window. |
| Not included | Bulk imports. |

**Result:** _(added if reached.)_
