from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_clone_install_entrypoints_exist_and_are_executable():
    install = ROOT / "scripts" / "install.sh"
    wrapper = ROOT / "scripts" / "hermes-kanban"
    env_example = ROOT / ".env.example"

    for path in [install, wrapper, env_example]:
        assert path.is_file(), path

    for path in [install, wrapper]:
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{path} should be executable by owner"


def test_install_script_supports_safe_clone_setup_contract():
    install = read("scripts/install.sh")

    for phrase in [
        "--dry-run",
        "--prefix",
        "--app-dir",
        "--env-file",
        "HERMES_KANBAN_WEBUI_APP_DIR",
        "HERMES_AGENT_ROOT",
        "uv sync",
        "python3",
        "hermes-kanban",
        "~/.local/bin",
        "~/.hermes/kanban-webui.env",
    ]:
        assert phrase in install

    assert "curl" not in install.lower(), "installer must not download or pipe remote code"


def test_hermes_kanban_wrapper_exposes_lifecycle_doctor_service_commands():
    wrapper = read("scripts/hermes-kanban")

    for phrase in [
        "start)",
        "stop)",
        "restart)",
        "status)",
        "logs)",
        "doctor)",
        "open)",
        "serve)",
        "service)",
        "service_install",
        "systemctl --user",
        "HERMES_KANBAN_WEBUI_ENV",
        "kanban-webui.pid",
        "/health",
        "server.py",
    ]:
        assert phrase in wrapper


def test_hermes_kanban_restart_can_continue_after_stop_helper():
    wrapper = read("scripts/hermes-kanban")

    assert 'restart) stop_cmd || true; start_cmd "$@" ;;' in wrapper
    assert 'exec "$APP_DIR/scripts/hermes-kanban-webui-stop"' not in wrapper


def test_env_example_is_localhost_first_and_secret_free():
    env = read(".env.example")

    for phrase in [
        "HERMES_KANBAN_WEBUI_HOST=127.0.0.1",
        "HERMES_KANBAN_WEBUI_PORT=8790",
        "HERMES_KANBAN_WEBUI_APP_DIR=",
        "HERMES_AGENT_ROOT=",
        "HERMES_KANBAN_WEBUI_STATE=",
        "HERMES_KANBAN_WEBUI_LOG=",
        "HERMES_KANBAN_WEBUI_ALLOWED_HOSTS=",
        "HERMES_KANBAN_WEBUI_TOKEN=",
    ]:
        assert phrase in env

    lowered = env.lower()
    for forbidden in ["/home/example-user", "example-tailnet", "discord", "api_key=", "token-placeholder"]:
        assert forbidden not in lowered


def test_readme_documents_one_command_install_and_management_flow():
    readme = read("README.md")

    for phrase in [
        "./scripts/install.sh",
        "hermes-kanban start",
        "hermes-kanban doctor",
        "hermes-kanban logs",
        "hermes-kanban service install",
        "~/.hermes/kanban-webui.env",
        "~/.local/bin/hermes-kanban",
    ]:
        assert phrase in readme


def test_readme_separates_hermes_core_and_webui_features_with_screenshots():
    readme = read("README.md")

    for phrase in [
        "Hermes Agent 기본 기능",
        "KanbanWebUI 추가 기능",
        "docs/assets/screenshots/kanban-board-overview.png",
        "docs/assets/screenshots/ai-workflow-designer.png",
    ]:
        assert phrase in readme

    for rel in [
        "docs/assets/screenshots/kanban-board-overview.png",
        "docs/assets/screenshots/ai-workflow-designer.png",
    ]:
        assert (ROOT / rel).is_file(), rel


def test_scripts_have_valid_bash_syntax():
    for rel in ["scripts/install.sh", "scripts/hermes-kanban"]:
        subprocess.run(["bash", "-n", str(ROOT / rel)], cwd=ROOT, check=True)


def test_install_dry_run_does_not_write_to_home(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    result = subprocess.run(
        ["bash", "scripts/install.sh", "--dry-run", "--prefix", str(tmp_path / "prefix")],
        cwd=ROOT,
        env={**os.environ, "HOME": str(fake_home)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert "DRY RUN" in result.stdout
    assert "hermes-kanban" in result.stdout
    assert not (fake_home / ".hermes" / "kanban-webui.env").exists()
    assert not (tmp_path / "prefix").exists()


def test_install_defaults_to_real_home_when_hermes_profile_home_is_active(tmp_path):
    fake_profile_home = tmp_path / "profiles" / "dev" / "home"
    real_home = tmp_path / "real-home"
    fake_profile_home.mkdir(parents=True)
    real_home.mkdir()

    result = subprocess.run(
        ["bash", "scripts/install.sh", "--dry-run", "--skip-uv-sync"],
        cwd=ROOT,
        env={
            **os.environ,
            "HOME": str(fake_profile_home),
            "HERMES_REAL_HOME": str(real_home),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert str(real_home / ".local" / "bin" / "hermes-kanban") in result.stdout
    assert str(real_home / ".hermes" / "kanban-webui.env") in result.stdout
    assert str(fake_profile_home / ".hermes" / "kanban-webui.env") not in result.stdout


def test_install_writes_real_home_based_env_file(tmp_path):
    fake_profile_home = tmp_path / "profiles" / "dev" / "home"
    real_home = tmp_path / "real-home"
    prefix = tmp_path / "prefix"
    env_file = tmp_path / "kanban-webui.env"
    fake_profile_home.mkdir(parents=True)
    real_home.mkdir()

    subprocess.run(
        [
            "bash",
            "scripts/install.sh",
            "--skip-uv-sync",
            "--prefix",
            str(prefix),
            "--env-file",
            str(env_file),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "HOME": str(fake_profile_home),
            "HERMES_REAL_HOME": str(real_home),
        },
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    env = env_file.read_text(encoding="utf-8")
    assert f'HERMES_REAL_HOME="{real_home}"' in env
    assert 'HERMES_AGENT_ROOT="${HERMES_REAL_HOME}/.hermes/hermes-agent"' in env
    assert 'HERMES_KANBAN_WEBUI_STATE="${HERMES_REAL_HOME}/.hermes/kanban-webui"' in env
    assert str(fake_profile_home) not in env
    assert (prefix / "bin" / "hermes-kanban").is_symlink()


def test_wrapper_logs_defaults_to_last_80_lines(tmp_path):
    log_path = tmp_path / "kanban.log"
    env_file = tmp_path / "kanban.env"
    log_path.write_text("\n".join(f"line {i}" for i in range(100)) + "\n", encoding="utf-8")
    env_file.write_text(
        f'HERMES_KANBAN_WEBUI_APP_DIR="{ROOT}"\n'
        f'HERMES_KANBAN_WEBUI_LOG="{log_path}"\n'
        f'HERMES_KANBAN_WEBUI_STATE="{tmp_path / "state"}"\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/hermes-kanban", "logs"],
        cwd=ROOT,
        env={**os.environ, "HERMES_KANBAN_WEBUI_ENV": str(env_file)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert "line 20" in result.stdout
    assert "line 99" in result.stdout
    assert "line 19" not in result.stdout
