# Issue #6 Responsive Progressive HermesKanban UI Overhaul Implementation Plan

> **For Hermes:** Route implementation through Kanban. Implementer should use TDD/static-contract tests first, regularly verify in browser at desktop and mobile widths, push a branch, and open/update a GitHub PR for review.

**Goal:** Make HermesKanban feel like a polished efficiency tool: compact, beautiful, responsive, and deeply aware of Hermes Agent Kanban concepts without making default cards noisy.

**Architecture:** Keep the current thin FastAPI + static ES-module UI. Improve the existing shell (`static/index.html`), board/card rendering (`static/board.js`), layout CSS (`static/style.css` + `static/design-tokens.css`), detail drawer (`static/drawer.js`), i18n strings (`static/i18n.js`), and focused tests (`tests/test_static_smoke.py`, plus browser QA evidence in the PR). Use progressive disclosure: default board shows only primary controls and scan-critical task metadata; secondary tools and Hermes worker/run/dependency details move behind menus/drawers/details.

**Tech Stack:** Python 3.14 via `uv`, FastAPI/Uvicorn, vanilla JavaScript ES modules, static CSS, pytest static-contract tests, browser QA against `http://100.100.51.16:8790/?board=hermes-kanban`.

---

## Grounding / Current Evidence

- GitHub issue: https://github.com/daily-language-3mins/HermesKanban/issues/6
- Repository: `/home/arios/projects/typescript/HermesKanban`
- Available profiles verified: `implementer`, `reviewer`, `planner`, `default`.
- Current branch during planning: `fix/config-default-language-zh-hant`.
- Current static smoke baseline: `python -m pytest tests/test_static_smoke.py -q` => `21 passed in 0.66s`.
- Browser desktop capture at `1280x639`, `?board=hermes-kanban` did select Hermes board correctly in the browser: `selectedBoard=hermes-kanban`.
- Browser console after load: no console messages and no JS errors.
- Layout metrics from browser: `document.documentElement.scrollWidth=1280`, `board.clientWidth=1244`, `board.scrollWidth=1704`; horizontal board overflow is intentional/contained but discoverability is weak.
- Screenshot evidence from planner browser QA: `/home/arios/.hermes/profiles/planner/cache/screenshots/browser_screenshot_3f623e2cd3a14265b0ec382e9a406258.png`.
- Visual issues confirmed: tall top chrome, overloaded toolbar, full KPI band duplicating column counts, repetitive empty-column helper text, verbose body previews/chips/drag hints on default cards, rightmost columns/cards visually clipped without a strong affordance.

---

## Non-goals

- Do not redesign the backend schema or Hermes Kanban worker protocol.
- Do not remove advanced features: Operations, AI Workflow, bulk create, dependency linking, worker logs, runs, comments, home-channel subscriptions must remain reachable.
- Do not make the default card a generic Trello clone; it should still surface Hermes-specific urgency such as blockers, running state, dependency count, PR/review hints when present.
- Do not rely on only static string tests; the PR must include browser screenshot evidence.

---

## Target UX Decisions

1. **Primary first:** top-level visible actions should be board select, search/filter, refresh, and one primary `新增任務` button. Secondary actions (`新增看板`, theme/language if space-constrained, Operations, AI Workflow, bulk create) go behind a compact `更多`/command menu or disclosure panel.
2. **Compact summary:** replace the always-heavy KPI card band with compact status chips integrated near column navigation or a collapsible summary row. Default view should show the board higher.
3. **Scan-friendly cards:** default card shows status/assignee/priority/title plus concise Hermes badges. Body preview is 0-2 lines max and can be hidden on narrow/mobile. Verbose metadata, full body, comments, run details, logs, dependency controls remain in the drawer.
4. **Hermes details in drawer:** worker runs, blockers, current claim/heartbeat health, parent/child dependencies, review/PR metadata (if present in metadata/body/comments), and logs should be grouped into readable drawer sections/accordions.
5. **Mobile as first-class:** no page-level horizontal overflow; controls collapse; card text remains readable; board column navigation/scroll affordance is obvious.

---

### Task 1: Add static contracts for progressive disclosure and compact shell

**Objective:** Lock the desired structure before changing layout.

**Files:**
- Modify: `tests/test_static_smoke.py`
- Read: `static/index.html`, `static/app.js`, `static/board.js`, `static/drawer.js`, `static/style.css`, `static/i18n.js`

**Step 1: Write failing tests**

Add tests that require:
- A secondary actions disclosure trigger in the shell, e.g. `id="moreActionsBtn"` and `id="moreActionsPanel"`, or an accessible equivalent.
- `Operations`, `建立 AI Workflow`, `批次新增`, and `新增看板` are not all always-visible toolbar buttons in the default toolbar.
- Compact board summary / status chips exist and the old full-height KPI visual contract is reduced or moved behind a compact class.
- Card rendering uses explicit primary/secondary metadata zones, e.g. `.card-primary-meta`, `.card-secondary-meta`, `.card-hermes-signal`, or equivalent names.
- Mobile CSS includes a control-collapse breakpoint and prevents page-level overflow.

Example assertions can be string-contract style like the current suite, but avoid overfitting exact CSS values except for critical overflow/accessibility constraints.

**Step 2: Verify failure**

Run: `python -m pytest tests/test_static_smoke.py -q`
Expected: FAIL on the new issue #6 contract tests.

**Step 3: Commit after implementation passes**

Do not commit yet in this task; commit after the matching implementation tasks below make the tests pass.

---

### Task 2: Refactor shell actions into progressive disclosure

**Objective:** Reduce top chrome/action overload while keeping all advanced actions reachable.

**Files:**
- Modify: `static/index.html:23-65`
- Modify: `static/app.js:104-123`
- Modify: `static/forms.js` if button IDs/events move
- Modify: `static/i18n.js` for `moreActions`, `closeActions`, `advancedActions`, etc.
- Modify: `static/style.css:18-44`, `235-272`
- Test: `tests/test_static_smoke.py`

**Implementation direction:**
- Keep `#boardSelect`, `#searchInput`, `#assigneeFilter`, `#refreshBtn`, and `#taskCreateBtn` easy to reach.
- Move secondary actions into a disclosure/menu:
  - `#newBoardBtn`
  - `#opsToggleBtn`
  - `#workflowBtn`
  - `#bulkBtn`
  - optionally `#themeToggle` and `#langToggle` on narrow widths while preserving accessibility.
- Implement menu open/close in `static/app.js` with `aria-expanded`, Escape-to-close, outside-click close, and keyboard focus support.
- Keep existing IDs for forms where possible so `forms.js`, `operations.js`, and current tests need minimal churn.

**Verification:**
- Run: `python -m pytest tests/test_static_smoke.py -q`
- Browser desktop: default top bar should be visibly shorter and primary vs secondary actions obvious.
- Browser console: no JS errors after opening/closing the secondary menu and launching each dialog/panel.

---

### Task 3: Compact board summary and column navigation

**Objective:** Make board content start higher while preserving status counts and navigation.

**Files:**
- Modify: `static/index.html:68-71`
- Modify: `static/board.js:43-67`
- Modify: `static/style.css:44-55`, `235-272`
- Modify: `static/i18n.js` if labels/tooltips are added
- Test: `tests/test_static_smoke.py`

**Implementation direction:**
- Replace full KPI card row default with compact status chips, either in `#columnNav` or a new compact summary bar.
- Keep counts accessible to screen readers and visually tied to statuses.
- On desktop, avoid spending a full tall row on duplicated counts; on mobile, keep the sticky column nav obvious.
- Empty columns should not repeat large helper cards; use a lighter placeholder or only show the `＋` column header affordance.

**Verification:**
- Run: `python -m pytest tests/test_static_smoke.py -q`
- Browser desktop: board columns begin higher than before; KPI/summary footprint is materially smaller.
- Browser mobile/narrow: column nav remains usable and not obscured by sticky headers.

---

### Task 4: Redesign task cards for scanability with Hermes signals

**Objective:** Keep default cards compact while highlighting what matters operationally.

**Files:**
- Modify: `static/board.js:11-40`
- Modify: `static/style.css:69-126`
- Modify: `static/i18n.js`
- Test: `tests/test_static_smoke.py`

**Implementation direction:**
- Default visible card fields:
  - task id in small mono text
  - localized status pill / status dot
  - title, clamped to 2 lines on desktop and 2-3 on mobile
  - assignee and priority
  - Hermes signal badges only when meaningful: blocked reason exists, running/live, parent/child count nonzero, comments nonzero, workflow step exists, review/PR metadata detected.
- Hide or reduce body preview by default:
  - desktop: max 1-2 lines, lower contrast
  - mobile: consider hiding preview unless card has no metadata
- Move drag hint/dependency port labels to hover/focus only; keep keyboard accessible.
- Empty-state helper text should be small and low-noise.

**Verification:**
- Run: `python -m pytest tests/test_static_smoke.py -q`
- Browser desktop: a user can scan title/status/assignee/priority without reading repository/body boilerplate.
- Keyboard: Tab to a card and press Enter/Space opens drawer; dependency ports remain reachable by focus/hover.

---

### Task 5: Progressive Hermes Agent details in the drawer

**Objective:** Expose deep Agent Kanban context without cluttering default cards.

**Files:**
- Modify: `static/drawer.js:172-242`
- Modify: `static/monitor.js` if run/heartbeat summaries are duplicated
- Modify: `static/style.css:128-168`, `210-234`
- Modify: `static/i18n.js`
- Test: `tests/test_static_smoke.py`

**Implementation direction:**
- Group drawer sections into logical progressive sections:
  - Overview / editable metadata
  - Blocker + lifecycle actions
  - Dependencies map
  - Worker runs / live monitor / claim health
  - Comments and events
  - Worker log
- Consider `<details>` for lower-priority sections; keep Overview, blocker status, and dependencies immediately visible.
- Surface PR/review status when available in task metadata/body/comments with safe heuristics:
  - URLs matching GitHub PRs or issues
  - metadata keys like `pr_url`, `pr_number`, `review_status`, `findings`, `tests_run`
  - Do not invent data; show only what exists.
- Keep existing API calls and actions intact.

**Verification:**
- Run: `python -m pytest tests/test_static_smoke.py -q`
- Browser: open running, blocked, and done task drawers; verify sections are readable and not one long wall.
- Console: no unhandled errors from tasks with missing metadata/runs/comments.

---

### Task 6: Mobile/narrow responsive hardening

**Objective:** Ensure the UI is usable at phone/narrow widths without page-level horizontal overflow.

**Files:**
- Modify: `static/style.css:235-272`
- Modify: `static/mobile.js` if context-menu/pointer fallback needs a clearer action path
- Modify: `static/index.html` if mobile menu markup is needed
- Test: `tests/test_static_smoke.py`

**Implementation direction:**
- Target breakpoints:
  - `>=1200px`: compact full board with horizontal board scroll only if columns exceed space.
  - `900-1199px`: compact header, grouped secondary actions, reduced summary row.
  - `<=760px`: single-column-width board carousel with sticky column nav and menuized controls.
  - `<=430px`: one-column control stack, no page-level overflow, dialogs/drawer fit viewport.
- Explicitly ensure: `document.documentElement.scrollWidth <= window.innerWidth + 1` on mobile viewport, except the internal `#board` may scroll horizontally.
- Avoid sticky top offsets that assume the old tall header; recalculate after top chrome reduction.

**Verification:**
- Run: `python -m pytest tests/test_static_smoke.py -q`
- Browser QA at desktop and mobile/narrow. If using Playwright/Selenium, capture:
  - desktop around `1280x720`
  - mobile around `390x844`
  - optional tablet `768x1024`
- Required JS checks in PR notes:
  - `window.innerWidth`, `document.documentElement.scrollWidth`, `#board.clientWidth`, `#board.scrollWidth`
  - console messages/errors after interactions.

---

### Task 7: Deep-link board selection fix/verification

**Objective:** Ensure `?board=hermes-kanban` reliably loads the intended board and updates state.

**Files:**
- Modify: `static/state.js:1-20`
- Modify: `static/app.js:13-31`, `83-102`, `107-111`
- Modify: `static/api.js` only if query helpers need changes
- Test: `tests/test_static_smoke.py`; add a focused JS/static contract test where practical

**Implementation direction:**
- On startup, parse `new URLSearchParams(location.search).get('board')` before localStorage fallback.
- If query board exists and appears in `/api/boards`, call `setBoard(queryBoard)` and select it.
- When board select changes, update both localStorage and URL query via `history.replaceState` without full reload.
- Preserve fallback behavior: if query/localStorage board does not exist, use `data.current` or first board.

**Verification:**
- Browser open: `http://100.100.51.16:8790/?board=hermes-kanban`
- Expected: board selector value is `hermes-kanban`, title is `Hermes Kanban WebUI`, board API uses `board=hermes-kanban`.
- Browser open without query should still use stored/current board appropriately.

---

### Task 8: Final QA, PR, and evidence

**Objective:** Produce a reviewable PR with automated and browser evidence.

**Files:**
- Update: PR description only; no extra code unless QA finds a defect.

**Required commands:**
- `python -m pytest tests/test_static_smoke.py -q`
- If practical: `python -m pytest -q`
- `git diff --check`
- `git status --short`

**Required browser QA evidence in PR:**
- Desktop screenshot after load at `?board=hermes-kanban`.
- Mobile/narrow screenshot after load at `?board=hermes-kanban`.
- Screenshot of secondary actions menu/disclosure open.
- Screenshot of a task drawer showing progressive Hermes details.
- Console result: no JS errors after load and after menu/drawer interactions.
- Board selection check: selector value and visible board title for `?board=hermes-kanban`.
- Overflow metrics for desktop and mobile.

**PR workflow:**
- Create a feature branch such as `ui/issue-6-progressive-responsive-overhaul`.
- Commit in logical chunks after tests pass.
- Push branch and create/update a PR against the repository default branch.
- Link issue #6 in PR body.
- If GitHub auth/remote credentials block push or PR creation, block the Kanban task with the exact missing action, e.g. `gh auth login` or missing remote permissions.

---

## Acceptance Criteria Summary

- Desktop: board content starts materially higher; top chrome and status summary are compact.
- Mobile: no page-level horizontal overflow; controls collapse into sensible menus; cards stay readable.
- Secondary features exist but are progressively disclosed.
- Cards prioritize title/status/assignee/priority and meaningful Hermes signals; verbose body/metadata moves to drawer/details.
- Drawer exposes worker runs, blockers, dependencies, PR/review/status metadata, comments/events/logs in grouped readable sections.
- `?board=hermes-kanban` deep-link behavior is verified and fixed if needed.
- Automated tests cover the new static/layout contracts where practical.
- PR includes desktop + mobile browser screenshots and console/overflow evidence.
