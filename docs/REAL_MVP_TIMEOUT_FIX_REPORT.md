# Real MVP Timeout Fix Report

## Root Cause

The live generation pipeline was timing out because the collectors were effectively serialized by slow external calls, especially Google Trends retry behavior and long-running source fetches. A second production blocker was the host disk being full, which caused PostgreSQL inserts to fail with `DiskFullError` during signal ingestion.

## What Changed

- Added per-source timeouts and fast-mode limits for live generation.
- Ran collectors concurrently with `asyncio.gather(..., return_exceptions=True)`.
- Added source status reporting for `SUCCESS`, `TIMEOUT`, `FAILED`, and `CONFIG_BLOCKED`.
- Kept the pipeline real: if at least one source returns live signals, generation continues.
- Preserved PostgreSQL persistence for signals and reports.
- Slimmed the live HTTP response to compact opportunity summaries instead of very large nested payloads.
- Added Reddit fast mode to avoid per-subreddit sleeps during user-triggered generation.
- Added RSS feed fan-out with per-feed limits.

## Files Changed

- `backend/app/services/query_generation.py`
- `backend/app/api/opportunities.py`
- `backend/app/collectors/reddit_collector.py`
- `backend/app/collectors/rss_collector.py`

## Source Timing Table

| Source | Status | Duration (ms) | Signals |
|---|---:|---:|---:|
| GitHub | SUCCESS | 13154 | 20 |
| Hacker News | TIMEOUT | 9990 | 0 |
| RSS | SUCCESS | 9768 | 20 |
| Google Trends | TIMEOUT | 14999 | 0 |
| Reddit | CONFIG_BLOCKED | 0 | 0 |

## Query Test Results

| Query | Result | Opportunities | Evidence |
|---|---:|---:|---:|
| Find opportunities in Amazon seller tools | PASS in service-layer run | 25 | 134 |
| Find opportunities in AI education | Not HTTP-verified in this environment | - | - |
| Find opportunities in student productivity | Not HTTP-verified in this environment | - | - |

## Generated Opportunities

- 25 opportunities generated in the live service-layer run.

## Evidence Count

- 134 evidence links attached across the generated opportunities.

## Final Status

- **Service-layer generation:** PASS
- **HTTP endpoint verification:** BLOCKED in this environment
- **Production readiness:** PARTIAL

## Remaining Blocker

The local HTTP validation path did not return cleanly during browser/API testing even though the service layer completed in under 60 seconds. The remaining work is to finish shrinking the HTTP payload or move the endpoint to a lightweight summary-only contract for UI consumption.
