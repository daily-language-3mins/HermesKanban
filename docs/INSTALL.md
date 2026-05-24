# Install Hermes KanbanWebUI

Hermes KanbanWebUI is distributed as a local clone plus a small lifecycle wrapper.
It uses your existing Hermes Agent Kanban SQLite database; it does not install a
new Hermes profile, dispatcher, or database.

## Requirements

- Linux, macOS, or WSL
- Python 3.11+
- `uv` on `PATH`
- Hermes Agent installed, or a Hermes Agent checkout at `~/.hermes/hermes-agent`
- For AI Workflow Designer: at least one usable Hermes profile that can run
  `hermes -p <profile> chat` for JSON-only planning

## Quick install

```bash
git clone https://github.com/daily-language-3mins/HermesKanban.git ~/.local/share/hermes-kanban
cd ~/.local/share/hermes-kanban
./scripts/install.sh
hermes-kanban doctor
hermes-kanban start
```

Open <http://127.0.0.1:8790>.

## What the installer creates

```text
~/.local/bin/hermes-kanban
~/.hermes/kanban-webui.env
~/.hermes/kanban-webui/
~/.hermes/logs/kanban-webui.log
```

The repository checkout stays where you cloned it. The wrapper stores that path
in `~/.hermes/kanban-webui.env` as `HERMES_KANBAN_WEBUI_APP_DIR`.

## AI Workflow Designer settings

The Workflow button opens a prompt-based designer. It asks a Hermes planner
profile to produce a draft DAG, lets you revise the draft, and only creates real
Kanban tasks when you click apply. Applying does not auto-dispatch workers.

Useful env values in `~/.hermes/kanban-webui.env`:

```bash
# Disable AI planner calls if you only want manual tasks.
HERMES_KANBAN_WORKFLOW_AI_ENABLED=true

# Optional. If empty, fallback is request value -> dev_plan -> default -> first profile on disk.
HERMES_KANBAN_WORKFLOW_PLANNER_PROFILE=

# Draft/attachment limits for text-like files.
HERMES_KANBAN_WORKFLOW_DEFAULT_MAX_STEPS=8
HERMES_KANBAN_WORKFLOW_MAX_STEPS=20
HERMES_KANBAN_WORKFLOW_ATTACHMENT_MAX_FILES=5
HERMES_KANBAN_WORKFLOW_ATTACHMENT_MAX_BYTES=200000
HERMES_KANBAN_WORKFLOW_PLANNER_TIMEOUT_SECONDS=180
```

Attachments are MVP text inputs: markdown, text, JSON/YAML/CSV, and source files
are read in the browser and sent as text. Binary/OCR/audio interpretation is not
part of this MVP.

After editing the env file, restart:

```bash
hermes-kanban restart
```

## Custom install paths

```bash
./scripts/install.sh \
  --prefix "$HOME/.local" \
  --env-file "$HOME/.hermes/kanban-webui.env" \
  --app-dir "$PWD"
```

Preview without writing:

```bash
./scripts/install.sh --dry-run
```

## Lifecycle commands

```bash
hermes-kanban start
hermes-kanban status
hermes-kanban logs
hermes-kanban logs -f
hermes-kanban restart
hermes-kanban stop
hermes-kanban open
hermes-kanban doctor
```

## systemd user service

If systemd user services are available:

```bash
hermes-kanban service install
hermes-kanban service start
hermes-kanban service status
```

If systemd is not available, use `hermes-kanban start`; it runs the server in
the background and records a pid file under `~/.hermes/kanban-webui/`.

## Update

```bash
hermes-kanban stop
cd ~/.local/share/hermes-kanban
git pull --ff-only
./scripts/install.sh
hermes-kanban start
```

## Uninstall wrapper and service

```bash
hermes-kanban service uninstall  # if installed
hermes-kanban stop
rm -f ~/.local/bin/hermes-kanban
rm -rf ~/.local/share/hermes-kanban
```

Optional local config/state cleanup:

```bash
rm -f ~/.hermes/kanban-webui.env
rm -rf ~/.hermes/kanban-webui
rm -f ~/.hermes/logs/kanban-webui.log
```

Do not delete `~/.hermes/kanban.db` unless you intentionally want to remove your
Hermes Kanban data.
