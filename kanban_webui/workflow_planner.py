"""Hermes CLI integration for AI workflow proposal generation."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from .config import Settings, real_user_home

JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class PlannerError(RuntimeError):
    """Raised when the planner cannot return a valid workflow proposal."""


def generate_workflow_proposal(
    *,
    prompt: str,
    planner_profile: str,
    max_steps: int,
    attachments: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    settings: Settings,
    previous_proposal: Optional[dict[str, Any]] = None,
    revision_prompt: Optional[str] = None,
) -> dict[str, Any]:
    """Ask a Hermes profile to design a workflow DAG and return JSON."""
    if not settings.workflow_ai_enabled:
        raise PlannerError("AI workflow planner is disabled")
    request = _build_prompt(
        prompt=prompt,
        max_steps=max_steps,
        attachments=attachments,
        profiles=profiles,
        previous_proposal=previous_proposal,
        revision_prompt=revision_prompt,
    )
    output = _run_hermes_planner(
        request,
        planner_profile=planner_profile,
        timeout=settings.workflow_planner_timeout_seconds,
    )
    return _extract_json_object(output)


def _run_hermes_planner(request: str, *, planner_profile: str, timeout: int) -> str:
    home = real_user_home()
    hermes_home = Path(os.environ.get("HERMES_HOME") or home / ".hermes").expanduser()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["HERMES_HOME"] = str(hermes_home)
    cmd = [
        "hermes",
        "-p",
        planner_profile,
        "chat",
        "-Q",
        "--ignore-rules",
        "--toolsets",
        "none",
        "--max-turns",
        "1",
        "--source",
        "kanban-webui-planner",
        "-q",
        request,
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed executable/argv, no shell
            cmd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PlannerError("hermes CLI was not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PlannerError(f"workflow planner timed out after {timeout}s") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise PlannerError(f"workflow planner failed: {detail[:1000]}")
    output = (completed.stdout or "").strip()
    if not output:
        raise PlannerError("workflow planner returned empty output")
    return output


def _build_prompt(
    *,
    prompt: str,
    max_steps: int,
    attachments: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    previous_proposal: Optional[dict[str, Any]],
    revision_prompt: Optional[str],
) -> str:
    profile_names = [item.get("name") for item in profiles if item.get("name")]
    attachment_lines: list[str] = []
    for item in attachments:
        attachment_lines.append(
            "\n".join(
                [
                    f"### {item.get('filename')}",
                    f"content_type: {item.get('content_type')}",
                    "excerpt:",
                    str(item.get("excerpt") or ""),
                ]
            )
        )
    previous = ""
    if previous_proposal:
        previous = "\n\n## Previous proposal JSON\n" + json.dumps(previous_proposal, ensure_ascii=False, indent=2)
    revision = ""
    if revision_prompt:
        revision = "\n\n## Revision request\n" + revision_prompt.strip()

    return f"""You design Hermes Kanban workflow DAGs.
Return ONLY one JSON object. No markdown, no commentary.

Schema:
{{
  "schema_version": 1,
  "title": "short workflow title",
  "summary": "what the workflow accomplishes",
  "strategy": "brief sequencing strategy",
  "applyable": true,
  "questions": ["optional blocking question strings"],
  "warnings": ["optional risk strings"],
  "steps": [
    {{
      "key": "stable_slug",
      "title": "task title",
      "body": "worker instructions",
      "assignee": "one of available profile names or null",
      "skills": ["optional Hermes skill names"],
      "priority": 0,
      "status": "ready|todo|triage",
      "depends_on": ["parent_step_key"],
      "acceptance_criteria": ["done condition"],
      "max_runtime_seconds": null
    }}
  ]
}}

Rules:
- Maximum steps: {max_steps}.
- Use a DAG only. No cycles. Every depends_on entry must reference another step key.
- Root executable steps should be status "ready" unless they need triage.
- Steps with dependencies should be status "todo".
- Available assignee profiles: {', '.join(profile_names) or '(none)'}.
- If no suitable profile exists, use null instead of inventing a profile.
- Keep task titles specific and bodies actionable for autonomous agents.

## User prompt
{prompt.strip()}

## Attachments
{chr(10).join(attachment_lines) if attachment_lines else '(none)'}{previous}{revision}
""".strip()


def _extract_json_object(output: str) -> dict[str, Any]:
    candidates = []
    fence = JSON_FENCE_RE.search(output)
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.append(output.strip())
    brace = _slice_json_object(output)
    if brace:
        candidates.append(brace)

    last_error: Optional[Exception] = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                raise PlannerError("planner JSON must be an object")
            return parsed
        except Exception as exc:  # keep trying extracted candidates
            last_error = exc
    raise PlannerError(f"planner did not return valid JSON: {last_error}")


def _slice_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]
