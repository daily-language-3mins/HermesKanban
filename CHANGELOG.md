# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Package-data based install support for `uv tool`/`pipx` once the runtime layout is stabilized.
- Optional generic Tailscale-only proxy template.

## [0.1.0] - 2026-05-05

### Added

- Standalone Hermes KanbanWebUI FastAPI service.
- Trello-style board UI with Korean default UI and English toggle.
- Board CRUD/switching, task creation, bulk creation, filtering, and drag-and-drop status changes.
- Task detail drawer, comments, events, runs, markdown rendering, and Live Run Monitor endpoints.
- Existing Hermes `hermes_cli.kanban_db` integration as the single source of truth.
- Optional header-based token auth.
- Host-header validation and cross-origin mutation blocking for safer localhost/Tailscale usage.
- Start/stop helper scripts and a systemd user-service template.
- Test suite for health/config, board endpoints, task lifecycle, auth, static shell, JavaScript syntax, drag/drop contract, Live Run Monitor, and CLI parity registry.

### Fixed

- Restored static JavaScript module loading by fixing the markdown newline replacement regex.
- Added static module cache-busting after the browser-facing JavaScript fix.

### Security

- Removed query-string token authentication.
- Prevented stored XSS in board select rendering.
- Added dependency-aware lifecycle handling for status updates.
- Rejected unknown Host headers and cross-site mutating browser requests.

[Unreleased]: https://github.com/PriuS2/HermesKanban/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/PriuS2/HermesKanban/releases/tag/v0.1.0
