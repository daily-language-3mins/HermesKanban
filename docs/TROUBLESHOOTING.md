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

## Workflow Designer planner fails

Check the WebUI log first:

```bash
hermes-kanban logs
```

Common causes:

- `HERMES_KANBAN_WORKFLOW_AI_ENABLED=0` disables planner calls.
- The selected planner profile does not exist on disk.
- Hermes CLI cannot chat from that profile because model/auth config is missing.
- The planner returned non-JSON or JSON that does not match the workflow schema.

Verify the profile outside the WebUI:

```bash
HOME="$HOME" HERMES_HOME="$HOME/.hermes" hermes -p dev_plan chat -Q -q 'Reply exactly: OK'
```

Use the actual planner profile if it is not `dev_plan`. If you want a specific
profile, set it in `~/.hermes/kanban-webui.env` and restart:

```bash
HERMES_KANBAN_WORKFLOW_PLANNER_PROFILE=dev_plan
hermes-kanban restart
```

If a generated task later fails with `Error: Unknown skill(s): kanban-worker`,
the task assignee profile has disabled the built-in `kanban-worker` skill. Remove
`kanban-worker` from that profile's `skills.disabled` list, then verify:

```bash
hermes -p <profile> skills list | grep kanban-worker
```

## Workflow attachment rejected

The MVP accepts text-like files only. Browser-side file reading sends text to the
server; binary/OCR/audio interpretation is not included. Adjust limits in
`~/.hermes/kanban-webui.env` if needed:

```bash
HERMES_KANBAN_WORKFLOW_ATTACHMENT_MAX_FILES=5
HERMES_KANBAN_WORKFLOW_ATTACHMENT_MAX_BYTES=200000
hermes-kanban restart
```

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
