"""Runtime settings for KanbanWebUI."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def real_user_home() -> Path:
    """Return the OS user's home, not Hermes profile HOME.

    Hermes Agent sessions may set HOME to ~/.hermes/profiles/<profile>/home.
    KanbanWebUI service state should live in /home/<user>/.hermes instead.
    """
    override = os.environ.get("HERMES_REAL_HOME")
    if override:
        return Path(override).expanduser()
    user = os.environ.get("USER")
    if user and (Path("/home") / user).exists():
        return Path("/home") / user
    return Path.home()


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8790
    log_path: Path = Path.home() / ".hermes" / "logs" / "kanban-webui.log"
    state_dir: Path = Path.home() / ".hermes" / "kanban-webui"
    token: str | None = None
    app_title: str = "Hermes KanbanWebUI"
    workflow_ai_enabled: bool = True
    workflow_planner_profile: Optional[str] = None
    workflow_default_max_steps: int = 8
    workflow_max_steps: int = 20
    workflow_attachment_max_files: int = 5
    workflow_attachment_max_bytes: int = 200_000
    workflow_planner_timeout_seconds: int = 180


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int, *, minimum: int = 1, maximum: Optional[int] = None) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def get_settings() -> Settings:
    user_home = real_user_home()
    host = os.environ.get("HERMES_KANBAN_WEBUI_HOST", "127.0.0.1")
    port = int(os.environ.get("HERMES_KANBAN_WEBUI_PORT", "8790"))
    log_path = Path(os.environ.get("HERMES_KANBAN_WEBUI_LOG", str(user_home / ".hermes" / "logs" / "kanban-webui.log"))).expanduser()
    state_dir = Path(os.environ.get("HERMES_KANBAN_WEBUI_STATE", str(user_home / ".hermes" / "kanban-webui"))).expanduser()
    token = os.environ.get("HERMES_KANBAN_WEBUI_TOKEN") or None
    workflow_max_steps = _env_int("HERMES_KANBAN_WORKFLOW_MAX_STEPS", 20, minimum=1, maximum=20)
    return Settings(
        host=host,
        port=port,
        log_path=log_path,
        state_dir=state_dir,
        token=token,
        workflow_ai_enabled=_env_bool("HERMES_KANBAN_WORKFLOW_AI_ENABLED", True),
        workflow_planner_profile=(os.environ.get("HERMES_KANBAN_WORKFLOW_PLANNER_PROFILE") or None),
        workflow_default_max_steps=_env_int("HERMES_KANBAN_WORKFLOW_DEFAULT_MAX_STEPS", 8, minimum=1, maximum=workflow_max_steps),
        workflow_max_steps=workflow_max_steps,
        workflow_attachment_max_files=_env_int("HERMES_KANBAN_WORKFLOW_ATTACHMENT_MAX_FILES", 5, minimum=0, maximum=20),
        workflow_attachment_max_bytes=_env_int("HERMES_KANBAN_WORKFLOW_ATTACHMENT_MAX_BYTES", 200_000, minimum=1024),
        workflow_planner_timeout_seconds=_env_int("HERMES_KANBAN_WORKFLOW_PLANNER_TIMEOUT_SECONDS", 180, minimum=5, maximum=600),
    )


ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
