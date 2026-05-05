# Hermes KanbanWebUI Troubleshooting

Start with:

```bash
hermes-kanban doctor
hermes-kanban status
hermes-kanban logs
```

## `hermes-kanban: command not found`

The installer writes the wrapper to `~/.local/bin/hermes-kanban` by default.
Ensure `~/.local/bin` is on `PATH`, or run the repo-local wrapper directly:

```bash
~/.local/bin/hermes-kanban doctor
./scripts/hermes-kanban doctor
```

## `uv not found`

Install `uv`, or set `UV=/absolute/path/to/uv` in
`~/.hermes/kanban-webui.env`.

## `Hermes not found` or `hermes_cli.kanban_db` import errors

Install Hermes Agent first, or point KanbanWebUI at an existing checkout:

```bash
HERMES_AGENT_ROOT="$HOME/.hermes/hermes-agent"
```

Set that value in `~/.hermes/kanban-webui.env`, then restart:

```bash
hermes-kanban restart
```

## Port already in use

Change the port in `~/.hermes/kanban-webui.env`:

```bash
HERMES_KANBAN_WEBUI_PORT=8791
```

Then restart:

```bash
hermes-kanban restart
```

## Browser shows `host not allowed`

The app only allows loopback hosts and explicitly configured hostnames. For a
trusted DNS/reverse-proxy/Tailscale hostname, add it to:

```bash
HERMES_KANBAN_WEBUI_ALLOWED_HOSTS=my-host.example.ts.net
```

Keep `HERMES_KANBAN_WEBUI_HOST=127.0.0.1` unless you intentionally need a
network bind, and set `HERMES_KANBAN_WEBUI_TOKEN` if exposing beyond localhost.

## API returns 401

If `HERMES_KANBAN_WEBUI_TOKEN` is set, clients must send one of:

```text
X-Kanban-Token: <token>
Authorization: Bearer <token>
```

Tokens are not accepted in query strings.

## systemd commands fail on WSL

Some WSL environments do not run systemd user services. Use the background
helper instead:

```bash
hermes-kanban start
hermes-kanban status
```
