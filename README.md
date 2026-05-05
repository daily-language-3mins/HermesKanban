# Hermes KanbanWebUI

Standalone, Trello-like WebUI for the Hermes Agent Kanban database.

KanbanWebUI is intentionally a thin Web/API layer over Hermes' existing
`hermes_cli.kanban_db` module. It does **not** create a new task schema,
dispatcher, or worker protocol. The Hermes CLI and this WebUI read/write the
same SQLite board data.

## Features

- Readable Trello-style board with columns for `triage`, `todo`, `ready`,
  `running`, `blocked`, and `done`.
- Quick task creation, bulk task creation, board CRUD/switching, filters, and
  drag-and-drop status changes.
- Task detail drawer with comments, events, runs, markdown rendering, and a
  Live Run Monitor for running tasks.
- Korean UI by default with an English toggle.
- Optional token auth for `/api/*` endpoints.
- Loopback-first runtime with Host-header and cross-origin mutation checks for
  safer localhost/Tailscale usage.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) on `PATH`
- A Hermes Agent source checkout or installation that exposes
  `hermes_cli.kanban_db`

If Hermes is not importable from your Python environment, set
`HERMES_AGENT_ROOT` to the Hermes Agent checkout that contains
`hermes_cli/kanban_db.py`:

```bash
export HERMES_AGENT_ROOT="$HOME/.hermes/hermes-agent"
```

## Quick start from Git

```bash
git clone https://github.com/PriuS2/HermesKanban.git
cd HermesKanban

# Only needed if hermes_cli is not already importable.
export HERMES_AGENT_ROOT="$HOME/.hermes/hermes-agent"

uv run python server.py --host 127.0.0.1 --port 8790
```

Open <http://127.0.0.1:8790>.

`uv run` creates/uses `.venv` automatically from `pyproject.toml`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `HERMES_AGENT_ROOT` | unset | Hermes Agent checkout containing `hermes_cli/kanban_db.py` when Hermes is not installed/importable. |
| `HERMES_KANBAN_WEBUI_HOST` | `127.0.0.1` | Bind host. Keep loopback unless you have a trusted reverse proxy/Tailscale-only proxy. |
| `HERMES_KANBAN_WEBUI_PORT` | `8790` | HTTP port. |
| `HERMES_KANBAN_WEBUI_STATE` | `$REAL_HOME/.hermes/kanban-webui` | Runtime state directory for pid files and local service metadata. |
| `HERMES_KANBAN_WEBUI_LOG` | `$REAL_HOME/.hermes/logs/kanban-webui.log` | Log file used by the helper script. |
| `HERMES_KANBAN_WEBUI_TOKEN` | unset | Optional API token. When set, `/api/*` and `/service/status` require auth. |
| `HERMES_KANBAN_WEBUI_ALLOWED_HOSTS` | unset | Comma-separated DNS hostnames allowed by Host-header validation, e.g. a Tailscale MagicDNS name. |
| `HERMES_REAL_HOME` | auto-detected | Override for the real OS home when running inside a Hermes profile HOME. |

State/log defaults resolve to the real OS home when possible, not to Hermes'
profile HOME such as `~/.hermes/profiles/<profile>/home`.

## Start/stop helper scripts

Run from a checked-out repo:

```bash
scripts/hermes-kanban-webui-start
scripts/hermes-kanban-webui-stop
```

If you copy the scripts to another directory such as `~/.local/bin`, also set
`HERMES_KANBAN_WEBUI_APP_DIR`:

```bash
export HERMES_KANBAN_WEBUI_APP_DIR="$HOME/workspace/HermesKanban"
hermes-kanban-webui-start
```

The start script uses `uv` from `PATH`, or `UV=/absolute/path/to/uv` if you need
to override it.

## systemd user service

A user-service template is provided at
`deploy/systemd/hermes-kanban-webui.service`.

Default assumptions in the template:

- repo checkout: `~/workspace/HermesKanban`
- Hermes checkout: `~/.hermes/hermes-agent`
- uv path available through `%h/.local/bin`
- bind address: `127.0.0.1:8790`

Install:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/hermes-kanban-webui.service ~/.config/systemd/user/
# Edit WorkingDirectory/HERMES_AGENT_ROOT if your paths differ.
systemctl --user daemon-reload
systemctl --user enable --now hermes-kanban-webui.service
systemctl --user status hermes-kanban-webui.service
```

## Optional auth

Local-only use has no token by default. To require auth on `/api/*` and
`/service/status`:

```bash
read -r HERMES_KANBAN_WEBUI_TOKEN < <(openssl rand -hex 32)
export HERMES_KANBAN_WEBUI_TOKEN
```

Clients should send either header:

```text
X-Kanban-Token: <token>
Authorization: Bearer <token>
```

Tokens are not accepted in query strings.

## Localhost, reverse proxy, and Tailscale security

- The app binds to `127.0.0.1` by default.
- Mutating methods reject cross-origin browser requests using `Origin`,
  `Referer`, and `Sec-Fetch-Site` checks.
- Unknown `Host` headers are rejected to reduce DNS-rebinding risk.
- Loopback IPs/names and Tailscale CGNAT IPs (`100.64.0.0/10`) are allowed.
- If you expose the service through a DNS name, set
  `HERMES_KANBAN_WEBUI_ALLOWED_HOSTS` to that hostname.
- If exposing beyond localhost, set `HERMES_KANBAN_WEBUI_TOKEN` and prefer a
  trusted reverse proxy or Tailscale-only proxy over binding to `0.0.0.0`.

Example for a Tailscale MagicDNS hostname:

```bash
export HERMES_KANBAN_WEBUI_ALLOWED_HOSTS="my-host.my-tailnet.ts.net"
read -r HERMES_KANBAN_WEBUI_TOKEN < <(openssl rand -hex 32)
export HERMES_KANBAN_WEBUI_TOKEN
uv run python server.py --host 127.0.0.1 --port 8790
```

Then expose `127.0.0.1:8790` through your chosen Tailscale/reverse-proxy setup.

## API highlights

- `GET /health`
- `GET /api/config`
- `GET /api/service/status`
- `POST /api/init`
- `GET/POST/PATCH/DELETE /api/boards...`
- `GET /api/board`
- `POST /api/tasks`
- `POST /api/tasks/bulk-create`
- `PATCH /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/claim`
- `POST /api/tasks/{task_id}/heartbeat`
- `POST /api/tasks/{task_id}/complete|block|unblock|archive`
- `GET /api/tasks/{task_id}/monitor`
- `GET /api/tasks/{task_id}/log|context|runs|events`
- `GET /api/events` and `GET /api/events/stream`
- `GET /api/stats`, `GET /api/assignees`
- `POST /api/dispatch` (`dry_run=true` by default; non-dry-run requires
  `confirm=dispatch`)
- `POST /api/gc` requires `confirm=gc`

## Tests

```bash
uv run --extra test python -m compileall -q kanban_webui server.py bootstrap.py
uv run --extra test python -m pytest -q
```

The suite covers health/config, board CRUD/switch, task lifecycle, Live Run
Monitor, auth, static shell, JavaScript syntax, drag/drop contract, and CLI
parity registry.

Optional design token check:

```bash
npx -y @google/design.md lint DESIGN.md
```

## CI

The recommended GitHub Actions workflow is included at `.github/workflows/ci.yml`.
It runs:

- Python 3.11 and 3.12 compile/test jobs.
- A checkout of `NousResearch/hermes-agent` so `hermes_cli.kanban_db` is available.
- JavaScript syntax checks for every static module.
- `DESIGN.md` lint.

## Release management

- License: Apache-2.0. See `LICENSE`.
- Version source: `pyproject.toml`.
- Human-written release notes: `CHANGELOG.md`.
- GitHub generated-release-note grouping: `.github/release.yml`.

Recommended release flow after merging to the default branch:

```bash
git checkout main
git pull origin main
uv run --extra test python -m pytest -q
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0" --notes-file CHANGELOG.md
```

## Installable package roadmap

The current supported distribution mode is clone-and-run. That is the safest
mode while KanbanWebUI depends on a local Hermes Agent checkout and serves
static assets directly from the repository.

To support `uv tool install` or `pipx install`, the project should next:

1. Move or package `static/` as Python package data.
2. Add a console entry point such as `hermes-kanban-webui`.
3. Update `kanban_webui.config.STATIC_DIR` to resolve packaged resources via
   `importlib.resources` instead of assuming a repo checkout.
4. Decide how to depend on Hermes Agent: PyPI package, git dependency, or
   explicit `HERMES_AGENT_ROOT` requirement.
5. Add a build check such as `uv build` to CI.

## Public distribution checklist

Completed:

- `LICENSE` file and matching `pyproject.toml` license metadata.
- GitHub Actions CI for Python tests, JavaScript syntax checks, and design lint.
- `CHANGELOG.md` and GitHub release-note configuration.

Still optional/future:

- Release tag/GitHub Release after merge to the default branch.
- Packaged install path/entry point if you want `pipx install` or `uv tool`
  usage instead of clone-and-run.

## Deferred

- Worker process kill/stop controls are intentionally out of MVP.
- Workflow Template Builder is intentionally out of MVP; implement after core
  board/API/CLI parity is stable.
