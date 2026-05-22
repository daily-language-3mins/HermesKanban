# Hermes KanbanWebUI Continuous Improvement Plan

> **For Hermes:** This is a measurement and planning artifact. Do not implement optimizations from this plan in the baseline task. Use follow-up implementer/reviewer Kanban cards for code changes.

**Goal:** Keep Hermes KanbanWebUI fast, reliable, and comfortable to use over Tailscale while preserving the thin-WebUI-over-Hermes-Kanban architecture.

**Architecture:** The app is a FastAPI service that serves static ES modules from `static/` and exposes `/api/*` routes over Hermes' existing `hermes_cli.kanban_db` SQLite layer. The current board UI loads config, board metadata, board payload, service status, optional update status, and event polling from the browser.

**Tech Stack:** Python 3.14 via `uv`, FastAPI/Uvicorn, SQLite through Hermes `kanban_db`, vanilla JavaScript ES modules, static CSS, Tailscale-bound HTTP service.

---

## Baseline Snapshot

Measured: 2026-05-22T18:33:47+08:00
Repository: `/home/arios/projects/typescript/HermesKanban`
Board: `hermes-kanban`
WebUI URL verified: `http://100.100.51.16:8790/`
Process observed: `uv run python server.py --host 100.100.51.16 --port 8790`
Current git state before this plan: existing uncommitted zh-Hant/i18n/static work in `static/*.js`, `static/index.html`, and `tests/test_static_smoke.py`; this plan intentionally does not edit those files.

### Origin endpoint timings

Command shape used for repeatable timing:

```bash
curl -sS --compressed \
  --connect-to localhost:8790:100.100.51.16:8790 \
  -o /tmp/hk_curl_body \
  -w 'code=%{http_code} ttfb=%{time_starttransfer} total=%{time_total} bytes=%{size_download}\n' \
  --max-time 30 "http://localhost:8790<endpoint>"
```

`--connect-to` keeps the URL host as `localhost` while reaching the Tailscale-bound service.

| Endpoint | HTTP | Transfer bytes | Median TTFB | Median total | Min-Max total |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/` | 200 | 9,672 | 1.3 ms | 1.5 ms | 1.3-2.6 ms |
| `/api/boards` | 200 | 890 | 2.6 ms | 2.7 ms | 2.6-2.8 ms |
| `/api/board?board=hermes-kanban` | 200 | 17,960 | 2.7 ms | 2.8 ms | 2.5-2.9 ms |
| `/api/config` | 200 | 2,385 | 1.3 ms | 1.4 ms | 1.3-1.6 ms |
| `/api/ops/summary?board=hermes-kanban` | 200 | 4,099 | 2.3 ms | 2.4 ms | 2.0-2.7 ms |

Interpretation: server-side origin work is currently fast for this small board. The main first-load delay is not FastAPI/SQLite latency; it is browser-critical path and external/static delivery behavior.

### Browser performance entries on Tailscale WebUI

Captured from `performance.getEntriesByType()` after loading `http://100.100.51.16:8790/` in the browser tool.

Navigation:

| Metric | Value |
| --- | ---: |
| `domInteractive` | 24 ms |
| `domContentLoadedEventEnd` | 3,061 ms |
| `loadEventEnd` | 3,745 ms |
| Document transfer | 9,972 bytes |
| Document decoded | 9,672 bytes |

Initial resource/API observations:

| Resource | Duration | Response end | Transfer | Decoded | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Google Fonts stylesheet | 3,038 ms | 3,056 ms | 1,254 B | 17,327 B | Blocks module execution / DOMContentLoaded path. |
| `/static/style.css` | 16 ms | 34 ms | 27,382 B | 27,082 B | Largest CSS asset. |
| `/static/app.js` | 16 ms | 34 ms | 6,988 B | 6,688 B | Entry module. |
| Static ES module graph, combined local JS | about 100 ms max resource duration | 145 ms latest local JS | about 101 KB transfer | about 96 KB decoded | Many separate module requests, but locally fast. |
| `/api/config` | 4 ms | 3,065 ms | 2,685 B | 2,385 B | Starts only after CSS/module execution. |
| `/api/boards` | 6 ms | 3,160 ms | 1,190 B | 890 B | Sequential after config. |
| `/api/board?board=hermes-kanban&include_archived=false` | 5 ms | 3,167 ms | 18,260 B | 17,960 B | Board visible shortly after this response/render. |
| `/api/service/status` | 51 ms | 3,251 ms | 926 B | 626 B | Runs after board render path. |
| `/api/app/update-status` | 1,997 ms | 5,058 ms | 755 B | 455 B | Non-blocking, but competes for startup and does a git fetch. |
| `/api/events?board=hermes-kanban&since=11` | 4-5 ms each | every 2.5 s | 358 B each | 58 B each | Expected polling; 8 duplicate URL entries observed over ~20 s. |

First visible board timing:
- Approximate first usable board: just after `/api/board?...` response at ~3.17 s from navigation start.
- The board itself has 7 visible cards and no console errors at capture time.
- If Google Fonts is cached or unavailable behavior changes, this number will move; record cold/warm loads separately in future work.

Console:
- `console_messages`: none after capture clear.
- `js_errors`: none.

Visual UI/UX observations from screenshot:
- Page is operational and readable; board selector, filters, KPIs, and task cards render.
- Horizontal board width exceeds the viewport; the rightmost `完成` column is partially cut off, and the horizontal scroll affordance is not obvious.
- Action/filter toolbar is dense, especially on the right side around Operations / create / workflow / bulk actions.
- Empty-column placeholders and dependency handle overlays create visual clutter near column tops.
- Task cards are readable but dense; long repository/remote body previews are truncated repeatedly and reduce scanability.
- UI currently mixes Chinese labels with English terms such as Operations, LIVE, and profile names; acceptable for dev users, but localization consistency should be tracked.

---

## Top 5 Bottlenecks / UX Friction Points

1. External Google Fonts stylesheet is on the critical path.
   - Evidence: fonts.googleapis.com stylesheet took 3,038 ms and DOMContentLoaded waited until ~3,061 ms. Local static assets and APIs were much faster.
   - Impact: first board visibility is around 3.17 s even though origin APIs are ~1-3 ms.

2. Initial API loading is sequential and not shaped around first paint.
   - Evidence: `load()` awaits `/api/config`, then `/api/boards`, then `/api/board`, then status/operations. Board data does not begin until config and boards complete.
   - Impact: low impact on this tiny board, but avoidable latency over slower Tailscale/proxy paths and larger boards.

3. Update check performs a remote git fetch on startup.
   - Evidence: `/api/app/update-status` took ~1,997 ms and calls `git fetch --quiet origin main` by default.
   - Impact: currently non-blocking, but it competes for browser/server attention at startup and can surface slow network noise unrelated to Kanban work.

4. Static/API responses are uncompressed and have weak delivery strategy for growth.
   - Evidence: no `Content-Encoding` on HTML, JSON, CSS, or JS despite `Accept-Encoding: gzip`; `/api/board` is already ~18 KB for 7 tasks, static JS/CSS is ~130 KB transfer plus fonts.
   - Impact: fine locally, but payload size will matter over tailnet/mobile/remote browsers and larger boards.

5. Board scanability and responsive affordances need another pass.
   - Evidence: partially clipped rightmost column, dense toolbar, repetitive long body previews, visually noisy dependency handles/empty placeholders.
   - Impact: user can operate the board, but scanning and deciding what to click requires unnecessary visual effort.

---

## Prioritized Roadmap

### Immediate 1: Remove external font from the critical path

**Objective:** Make first board visibility independent of Google Fonts latency.

**Files likely involved:**
- Modify: `static/index.html`
- Modify: `static/style.css` or `static/design-tokens.css`
- Test: `tests/test_static_smoke.py`

**Implementation direction:**
- Prefer system font stack by default: `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- Either remove the Google Fonts `<link>` entirely or move it behind a non-blocking/local-font strategy.
- Keep JetBrains Mono fallback as `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`.

**Acceptance criteria:**
- Cold-load browser capture shows no `fonts.googleapis.com` critical resource, or the resource no longer gates `domContentLoaded`.
- First visible board is under 1.0 s on the same Tailscale URL when APIs remain local-fast.
- No visible typography regression that makes zh-Hant or code chips harder to read.
- `uv run --extra test pytest -q` passes.

### Immediate 2: Parallelize startup data fetches and render progressively

**Objective:** Start board data earlier and show useful skeleton/status while optional data loads.

**Files likely involved:**
- Modify: `static/app.js`
- Modify: `static/board.js`
- Modify: `static/operations.js`
- Test: add/update static smoke tests if current suite validates load ordering.

**Implementation direction:**
- Fetch `/api/config` and `/api/boards` in parallel where possible.
- Render board as soon as `/api/board` returns; load `/api/service/status` and operations panel after board paint.
- Keep operations summary lazy; only fetch when panel is open.
- Add a minimal loading/empty/error state for each panel instead of a single all-or-nothing startup.

**Acceptance criteria:**
- Performance entries show `/api/config` and `/api/boards` overlapping.
- Board render is not delayed by `/api/service/status`, operations, or update checks.
- Search/filter/board switch behavior remains correct.
- Console remains free of unhandled promise errors.
- `uv run --extra test pytest -q` passes.

### Immediate 3: Defer and cache app update status

**Objective:** Keep git/network update checks from affecting the first-load experience.

**Files likely involved:**
- Modify: `static/update.js`
- Modify: `kanban_webui/app_update.py`
- Modify: `kanban_webui/kanban_api.py`
- Test: app update status unit/static tests.

**Implementation direction:**
- Delay update check until after first board render and/or idle callback.
- Add a cached fast status endpoint mode that does not fetch remote on every initial page load.
- Keep explicit user-triggered update check capable of fetching remote.

**Acceptance criteria:**
- No `/api/app/update-status` request before the first board paint in startup performance entries.
- Automatic update prompt still appears within a reasonable background window when updates exist.
- Dirty working tree and non-main safety behavior remains unchanged.
- `uv run --extra test pytest -q` passes.

### Next 1: Add compression and static cache headers

**Objective:** Improve remote/tailnet transfer efficiency without changing API semantics.

**Files likely involved:**
- Modify: `kanban_webui/app.py`
- Modify: tests covering headers/static smoke.

**Implementation direction:**
- Add FastAPI `GZipMiddleware(minimum_size=1000)` or equivalent.
- Add long-lived immutable cache headers for versioned static assets containing `?v=...`.
- Add conservative `no-store` or short cache headers for dynamic `/api/*` responses.

**Acceptance criteria:**
- `curl --compressed` against `/api/board?board=hermes-kanban` shows `Content-Encoding: gzip` when payload exceeds threshold.
- Static JS/CSS revalidation/transfer drops on warm reload where browser cache is allowed.
- API freshness remains correct after task changes.
- `uv run --extra test pytest -q` passes.

### Next 2: Improve board responsive layout and scanability

**Objective:** Make the board easier to scan and operate on laptop/mobile widths.

**Files likely involved:**
- Modify: `static/style.css`
- Modify: `static/board.js`
- Modify: `static/dependency-lines.js`
- Modify: `static/mobile.js`
- Test: static smoke and manual browser observations.

**Implementation direction:**
- Add clear horizontal scroll affordance or column navigation state.
- Reduce toolbar density by grouping secondary actions.
- Make long task body previews less repetitive, e.g. shorter preview with metadata chips, expand on drawer.
- Reduce default visual weight of dependency handles/empty placeholders until hover/focus.

**Acceptance criteria:**
- Rightmost columns are discoverable without guessing; column navigation or scroll hint is visible.
- Cards show title, assignee/status/priority, and concise preview without burying the task list.
- Dependency creation affordance remains keyboard/mouse accessible.
- Browser screenshot shows less overlay clutter in the default board view.
- `uv run --extra test pytest -q` passes.

### Next 3: Add lightweight performance instrumentation

**Objective:** Make future regressions measurable without manual DevTools work.

**Files likely involved:**
- Create/modify: `static/performance.js` or `static/app.js`
- Modify: `kanban_webui/kanban_api.py` if server-side timing endpoint is desired
- Create/modify: docs/testing notes

**Implementation direction:**
- Emit marks for `kanban:start`, `kanban:board-data-received`, `kanban:board-rendered`, `kanban:first-interactive`.
- Log metrics only in dev/debug mode or expose a copyable diagnostics panel.
- Include resource summary: API count, duplicated URLs, total transfer, console errors.

**Acceptance criteria:**
- Browser console can report first board render without hand-written snippets.
- Metrics are disabled or quiet by default for normal users.
- No PII/task body dumps in telemetry output.
- `uv run --extra test pytest -q` passes.

### Later 1: Scale `/api/board` for large boards

**Objective:** Keep board usable when a board has hundreds or thousands of tasks.

**Files likely involved:**
- Modify: `kanban_webui/kanban_api.py`
- Modify: `static/api.js`
- Modify: `static/board.js`
- Tests for pagination/filtering compatibility.

**Implementation direction:**
- Add server-side pagination/filter windows or column-scoped loading.
- Keep current full payload path for compatibility until the UI is migrated.
- Push search/filter work server-side when board size crosses a threshold.

**Acceptance criteria:**
- Synthetic large board benchmark documents `/api/board` latency and payload before/after.
- Initial visible columns render from bounded payloads.
- Search/filter semantics remain correct.
- `uv run --extra test pytest -q` passes.

### Later 2: Move polling toward event stream with safe fallback

**Objective:** Reduce recurring duplicate `/api/events` requests and improve freshness.

**Files likely involved:**
- Modify: `static/app.js`
- Modify: `kanban_webui/kanban_api.py`
- Tests for event fallback.

**Implementation direction:**
- Prefer `/api/events/stream` with exponential reconnect/backoff.
- Keep current 2.5 s polling as fallback for browsers/proxies that do not support SSE reliably.

**Acceptance criteria:**
- Performance entries no longer accumulate duplicate `/api/events?...` fetches during normal browsing when SSE works.
- Task updates still refresh the board within 1-2 s.
- Fallback polling activates after stream failure.
- `uv run --extra test pytest -q` passes.

### Later 3: Bundle or prebuild static assets when install mode allows

**Objective:** Reduce module-request overhead and enable content-hashed static assets for long-term caching.

**Files likely involved:**
- Add build tooling only if the project accepts a build step.
- Modify installer/service docs if build artifacts become part of release.

**Implementation direction:**
- Keep the no-build development path unless the operational gain is worth added complexity.
- If bundling is introduced, require generated assets to be deterministic and easy to inspect.

**Acceptance criteria:**
- Warm load transfers less static JS/CSS over Tailscale.
- Install/update path remains simple and documented.
- Static smoke tests cover built asset references.
- `uv run --extra test pytest -q` passes.

---

## Recommended Task Order

1. Remove external font critical path.
2. Parallelize startup fetches and render board before optional status/update work.
3. Defer/cache update-status git fetch.
4. Add compression and cache headers.
5. Polish responsive board scanability and dependency/empty-state affordances.
6. Add built-in performance instrumentation.
7. Scale `/api/board` for large boards.
8. Replace steady polling with SSE plus fallback.
9. Consider static bundling/content hashing only after the no-build path is stable.

This order targets the measured first-load delay first, then payload/delivery resilience, then UI comfort and future scale.

---

## Verification Checklist for Follow-up Cards

Every implementation card spawned from this plan should include:

- Preserve unrelated zh-Hant/i18n work unless explicitly touching those files.
- Do not edit `~/.hermes/kanban.db` or board DB files directly; use Hermes CLI/API only.
- Re-run origin timing for the affected endpoints.
- Re-run browser performance capture on `http://100.100.51.16:8790/`.
- Record console errors and visual observations.
- Run `uv run --extra test pytest -q` before handoff.
- Push a focused branch and create/update a PR if code changes are ready for review.
