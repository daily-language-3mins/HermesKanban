# Install Hermes KanbanWebUI

Hermes KanbanWebUI is distributed as a local clone plus a small lifecycle wrapper.
It uses your existing Hermes Agent Kanban SQLite database; it does not install a
new Hermes profile, dispatcher, or database.

## Requirements

- Linux, macOS, or WSL
- Python 3.11+
- `uv` on `PATH`
- Hermes Agent installed, or a Hermes Agent checkout at `~/.hermes/hermes-agent`

## Quick install

```bash
git clone https://github.com/PriuS2/HermesKanban.git ~/.local/share/hermes-kanban
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
