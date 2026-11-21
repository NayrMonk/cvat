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
| How | `curl -s -o /dev/null -w "%{time_total}"` against `http://localhost:8080` with the session cookie a logged-in browser sends (see "Change of method" below). One warm-up request is discarded. A run is 20 sequential requests, and the run's value is their median. |
| Target | Median of 5 runs at or below **100 ms**. |
| Conditions | Local Docker stack, nothing else running, the same task each time, no other requests in flight. |
| Not included | The first request after a container start, browser rendering, WebSocket delivery. |

**Why 100 ms:** every live change makes the page fetch again, so the endpoint's cost repeats for every change, for
every open page. 100 ms keeps a live update looking immediate. It is also tight enough that permission checks plus
counting ~41.9k stored shapes (the 36.8k COCO annotations, with multi-part polygons split) could plausibly miss it.

**Result: target met.** Median of the 5 run medians **44.7 ms** (run medians 44.6 to 49.4 ms), against a
target of 100 ms. The target was cleared with room to spare, so I did not move it after measuring.

Raw output:

```
# MO-1 raw output, 2026-11-21T11:39:03Z
# GET http://localhost:8080/api/annotation-stats/tasks/1  (task 1: 5000 images, 41866 shapes), session cookie, curl %{time_total} in ms, 1 warm-up discarded
run 1 samples: 42.3 43.2 43.0 46.2 43.3 50.9 47.5 52.3 51.9 62.8 60.1 60.9 58.3 48.4 62.1 49.0 49.7 44.2 51.0 46.3 
run 1 median=49.4 min=42.3 max=62.8
run 2 samples: 42.6 42.7 44.7 48.6 42.6 44.7 43.9 44.3 44.1 46.8 44.6 43.5 47.7 42.7 43.2 56.9 58.3 65.2 54.8 47.3 
run 2 median=44.7 min=42.6 max=65.2
run 3 samples: 59.0 62.1 54.1 45.6 45.9 45.8 49.7 43.6 47.7 45.1 42.5 43.9 43.6 42.6 42.7 44.9 44.4 43.4 46.9 42.4 
run 3 median=45.0 min=42.4 max=62.1
run 4 samples: 45.9 45.9 43.1 43.5 42.3 44.7 44.3 44.1 46.2 48.6 44.5 42.7 44.2 45.8 52.3 43.8 46.1 44.1 47.5 44.9 
run 4 median=44.6 min=42.3 max=52.3
run 5 samples: 62.7 43.4 43.5 44.0 44.6 43.1 47.4 43.9 46.2 45.2 44.8 43.1 45.1 44.7 44.6 44.3 44.7 47.3 43.8 50.7 
run 5 median=44.7 min=43.1 max=62.7
```

**Change of method.** The plan said Basic auth. A pilot of 5 requests showed why that is wrong: with Basic auth the
median was 240 ms (min 232, max 284), against 47 ms with the session cookie. Basic auth makes Django hash the password
on every request, so that number measures password hashing, not this endpoint. The UI always sends the session
cookie, so the cookie is the path users actually hit, and the formal run above uses it.

**Where the 44.7 ms goes** (inside `cvat_server`, same task):

```
count_annotations_by_label(task 1): median 18.2 ms (min 16.8, max 25.3), 15 runs
SQL queries issued: 4
users/self median=9.5 ms
```

Roughly: 9.5 ms is the floor for any authenticated CVAT request (nginx, uvicorn, session lookup), 18 ms is the
counting itself (4 SQL queries), and the remaining ~17 ms is the task lookup, the access check and serialising the
response. I did not isolate that last part, so I do not claim it is all the access check.

## MO-2 — live update latency (stretch)

| Field | Entry |
|---|---|
| What is measured | Time from saving a new box in a job to the stats page in another tab showing the new count. |
| How | `performance.now()` logged in the browser console when the WebSocket message arrives and when the chart re-renders with new data, plus the save request's end time from the network panel. |
| Target | Median of 5 runs at or below **1 s**. |
| Conditions | Same as MO-1, two tabs in one Chrome window. |
| Not included | Bulk imports. |

**Result:** _(added if reached.)_
