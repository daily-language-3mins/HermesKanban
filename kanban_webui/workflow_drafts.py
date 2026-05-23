"""Prompt-driven workflow draft storage and validation."""
from __future__ import annotations

import json
import re
import secrets
import shutil
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Optional

from .config import Settings
from .hermes_imports import kanban_db

DRAFT_PREFIX = "wfd_"
PROMPT_WORKFLOW_SOURCE_ID = "prompt-generated-v1"
PROMPT_WORKFLOW_SOURCE_NAME = "AI Workflow Designer"
DRAFT_RE = re.compile(r"^wfd_[A-Za-z0-9][A-Za-z0-9._-]*$")
STEP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._ -]+")
ALLOWED_STEP_STATUSES = {"ready", "todo", "triage"}
MAX_TITLE_CHARS = 240
MAX_BODY_CHARS = 12_000
MAX_EXCERPT_CHARS = 1_200


class DraftError(ValueError):
    """Raised when a workflow draft cannot be loaded or mutated."""


def new_draft_id() -> str:
    return f"{DRAFT_PREFIX}{int(time.time())}_{secrets.token_hex(4)}"


def validate_draft_id(draft_id: str) -> str:
    if not DRAFT_RE.match(str(draft_id or "")):
        raise DraftError("invalid workflow draft id")
    return draft_id


def drafts_root(settings: Settings) -> Path:
    return settings.state_dir / "workflow-drafts"


def archived_drafts_root(settings: Settings) -> Path:
    return settings.state_dir / "workflow-drafts-archive"


def draft_dir(settings: Settings, draft_id: str) -> Path:
    return drafts_root(settings) / validate_draft_id(draft_id)


def draft_json_path(settings: Settings, draft_id: str) -> Path:
    return draft_dir(settings, draft_id) / "draft.json"


def available_profiles(conn) -> list[dict[str, Any]]:
    """Return on-disk Hermes profiles suitable for planner/assignee choices."""
    profiles = [dict(item) for item in kanban_db.known_assignees(conn) if item.get("on_disk")]
    if not profiles:
        profiles = [{"name": name, "on_disk": True, "counts": {}} for name in kanban_db.list_profiles_on_disk()]
    return sorted(profiles, key=lambda item: item.get("name") or "")


def profile_names(profiles: Iterable[dict[str, Any]]) -> list[str]:
    return [str(item.get("name")) for item in profiles if item.get("name")]


def select_planner_profile(
    requested: Optional[str],
    *,
    settings: Settings,
    profiles: list[dict[str, Any]],
) -> str:
    """Resolve planner profile without assuming every installation has dev_plan."""
    names = profile_names(profiles)
    known = set(names)

    def usable(value: Optional[str]) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        if known and text not in known:
            raise DraftError(f"planner_profile {text!r} is not an available on-disk profile")
        return text

    explicit = usable(requested)
    if explicit:
        return explicit
    env_profile = usable(settings.workflow_planner_profile)
    if env_profile:
        return env_profile
    if "dev_plan" in known:
        return "dev_plan"
    if "default" in known:
        return "default"
    if names:
        return names[0]
    return "default"


def normalize_attachment_inputs(
    draft_path: Path,
    attachments: Iterable[dict[str, Any]],
    *,
    max_files: int,
    max_bytes: int,
) -> list[dict[str, Any]]:
    items = list(attachments or [])
    if len(items) > max_files:
        raise DraftError(f"at most {max_files} attachment files are allowed")

    attachment_dir = draft_path / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    normalized: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for index, item in enumerate(items, start=1):
        filename = _sanitize_filename(str(item.get("filename") or f"attachment-{index}.txt"))
        stored_name = _dedupe_filename(filename, used_names)
        used_names.add(stored_name)
        content = item.get("content") or ""
        if not isinstance(content, str):
            raise DraftError(f"attachment {filename!r} content must be text for MVP")
        encoded = content.encode("utf-8")
        if len(encoded) > max_bytes:
            raise DraftError(f"attachment {filename!r} exceeds {max_bytes} bytes")
        path = attachment_dir / stored_name
        path.write_text(content, encoding="utf-8")
        normalized.append(
            {
                "id": f"att_{index}",
                "filename": filename,
                "stored_name": stored_name,
                "path": str(path),
                "content_type": item.get("content_type") or "text/plain",
                "size_bytes": len(encoded),
                "text_available": True,
                "excerpt": _excerpt(content),
            }
        )
    return normalized


def normalize_proposal(
    proposal: dict[str, Any],
    *,
    available_profile_names: Iterable[str],
    max_steps: int,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    errors: list[str] = []
    warnings: list[str] = []
    raw = deepcopy(proposal or {})
    known_profiles = set(available_profile_names or [])

    if not isinstance(raw, dict):
        return {}, {"errors": ["proposal must be a JSON object"], "warnings": []}

    try:
        schema_version = int(raw.get("schema_version"))
    except Exception:
        schema_version = None
    if schema_version != 1:
        errors.append("schema_version must be 1")

    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    strategy = str(raw.get("strategy") or "").strip()
    if not title:
        errors.append("proposal title is required")
    if not summary:
        errors.append("proposal summary is required")

    steps_raw = raw.get("steps") or []
    if not isinstance(steps_raw, list) or not steps_raw:
        errors.append("proposal must include at least one step")
        steps_raw = []
    if len(steps_raw) > max_steps:
        errors.append(f"proposal has {len(steps_raw)} steps, max_steps is {max_steps}")

    normalized_steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    step_keys: list[str] = []
    for index, step in enumerate(steps_raw, start=1):
        if not isinstance(step, dict):
            errors.append(f"step {index} must be an object")
            continue
        key = str(step.get("key") or step.get("step_key") or "").strip()
        if not STEP_RE.match(key):
            errors.append(f"invalid step key: {key!r}")
        if key in seen:
            errors.append(f"duplicate step key: {key}")
        seen.add(key)
        step_keys.append(key)

        step_title = str(step.get("title") or "").strip()
        if not step_title:
            errors.append(f"step {key or index} title is required")
        if len(step_title) > MAX_TITLE_CHARS:
            errors.append(f"step {key or index} title is too long")

        body = str(step.get("body") or "").strip()
        if len(body) > MAX_BODY_CHARS:
            errors.append(f"step {key or index} body is too long")
            body = body[:MAX_BODY_CHARS]

        depends_on = _string_list(step.get("depends_on") or [])
        status = str(step.get("status") or ("todo" if depends_on else "ready")).strip() or "ready"
        if status not in ALLOWED_STEP_STATUSES:
            errors.append(f"step {key or index} status must be one of {sorted(ALLOWED_STEP_STATUSES)}")
            status = "todo" if depends_on else "ready"
        if depends_on and status == "ready":
            status = "todo"
            warnings.append(f"step {key} depends on parent steps, so status was normalized to todo")

        assignee = step.get("assignee")
        if assignee is not None:
            assignee = str(assignee).strip() or None
        if assignee and known_profiles and assignee not in known_profiles:
            warnings.append(f"assignee {assignee!r} is not an on-disk profile and was cleared")
            assignee = None

        priority = step.get("priority", 0)
        try:
            priority = int(priority)
        except Exception:
            errors.append(f"step {key or index} priority must be an integer")
            priority = 0

        max_runtime = step.get("max_runtime_seconds")
        if max_runtime in ("", 0):
            max_runtime = None
        if max_runtime is not None:
            try:
                max_runtime = int(max_runtime)
            except Exception:
                errors.append(f"step {key or index} max_runtime_seconds must be an integer or null")
                max_runtime = None

        normalized_steps.append(
            {
                "key": key,
                "step_key": key,
                "title": step_title,
                "body": body,
                "assignee": assignee,
                "skills": _normalize_skills(step.get("skills") or [], errors, key or str(index)),
                "priority": priority,
                "status": status,
                "depends_on": depends_on,
                "acceptance_criteria": _string_list(step.get("acceptance_criteria") or []),
                "max_runtime_seconds": max_runtime,
            }
        )

    known_steps = set(step_keys)
    graph = {key: [] for key in step_keys if key}
    for step in normalized_steps:
        for parent in step.get("depends_on") or []:
            if parent not in known_steps:
                errors.append(f"step {step['key']} depends on unknown step {parent}")
            else:
                graph.setdefault(parent, []).append(step["key"])
    if _has_cycle(graph):
        errors.append("workflow step graph cannot contain cycles")

    warnings.extend(_string_list(raw.get("warnings") or []))
    normalized = {
        "schema_version": 1,
        "title": title[:MAX_TITLE_CHARS],
        "summary": summary,
        "strategy": strategy,
        "applyable": bool(raw.get("applyable", True)) and not errors,
        "questions": _string_list(raw.get("questions") or []),
        "warnings": warnings,
        "steps": normalized_steps,
    }
    return normalized, {"errors": errors, "warnings": warnings}


def create_draft_record(
    *,
    settings: Settings,
    board: str,
    prompt: str,
    planner_profile: str,
    max_steps: int,
    attachments: list[dict[str, Any]],
    proposal: dict[str, Any],
    validation: dict[str, list[str]],
    profiles: list[dict[str, Any]],
    draft_id: Optional[str] = None,
) -> dict[str, Any]:
    draft_id = validate_draft_id(draft_id or new_draft_id())
    now = int(time.time())
    draft = {
        "draft_id": draft_id,
        "board": board,
        "status": "draft",
        "revision": 1,
        "created_at": now,
        "updated_at": now,
        "applied_at": None,
        "applied_instance_id": None,
        "prompt": prompt,
        "planner_profile": planner_profile,
        "max_steps": max_steps,
        "attachments": attachments,
        "proposal": proposal,
        "validation": validation,
        "profiles": profiles,
        "revisions": [
            {
                "revision": 1,
                "created_at": now,
                "prompt": prompt,
                "revision_prompt": None,
                "proposal": proposal,
                "validation": validation,
            }
        ],
    }
    save_draft(settings, draft)
    return draft


def load_draft(settings: Settings, draft_id: str) -> dict[str, Any]:
    path = draft_json_path(settings, draft_id)
    if not path.is_file():
        raise FileNotFoundError(draft_id)
    return json.loads(path.read_text(encoding="utf-8"))


def save_draft(settings: Settings, draft: dict[str, Any]) -> None:
    target_dir = draft_dir(settings, draft["draft_id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "draft.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def append_revision(
    settings: Settings,
    draft: dict[str, Any],
    *,
    revision_prompt: str,
    proposal: dict[str, Any],
    validation: dict[str, list[str]],
) -> dict[str, Any]:
    if draft.get("status") == "applied":
        raise DraftError("applied workflow drafts cannot be revised; fork/create a new draft")
    now = int(time.time())
    revision = int(draft.get("revision") or 1) + 1
    draft["revision"] = revision
    draft["updated_at"] = now
    draft["proposal"] = proposal
    draft["validation"] = validation
    draft.setdefault("revisions", []).append(
        {
            "revision": revision,
            "created_at": now,
            "prompt": draft.get("prompt"),
            "revision_prompt": revision_prompt,
            "proposal": proposal,
            "validation": validation,
        }
    )
    save_draft(settings, draft)
    return draft


def mark_applied(settings: Settings, draft: dict[str, Any], *, instance_id: str, result: dict[str, Any]) -> dict[str, Any]:
    if draft.get("status") == "applied":
        raise DraftError("workflow draft has already been applied")
    now = int(time.time())
    draft["status"] = "applied"
    draft["updated_at"] = now
    draft["applied_at"] = now
    draft["applied_instance_id"] = instance_id
    draft["apply_result"] = result
    save_draft(settings, draft)
    return draft


def remove_draft(
    settings: Settings,
    draft: dict[str, Any],
    *,
    archive: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Delete or archive a workflow draft directory and its attachments.

    Drafts are stored as one directory containing draft.json and an attachments/
    subdirectory. Removing the directory is therefore the authoritative cleanup
    operation for both metadata and uploaded attachment files.
    """
    draft_id = validate_draft_id(str(draft.get("draft_id") or ""))
    source = draft_dir(settings, draft_id)
    if draft.get("status") == "applied" and not archive and not force:
        raise DraftError("applied workflow drafts require force=true for hard delete")
    if not source.exists():
        raise FileNotFoundError(draft_id)

    if archive:
        now = int(time.time())
        target_root = archived_drafts_root(settings)
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / f"{draft_id}-{now}"
        suffix = 2
        while target.exists():
            target = target_root / f"{draft_id}-{now}-{suffix}"
            suffix += 1
        archived = deepcopy(draft)
        archived["status"] = "archived"
        archived["updated_at"] = now
        archived["archived_at"] = now
        archived["archived_from_status"] = draft.get("status") or "draft"
        save_draft(settings, archived)
        shutil.move(str(source), str(target))
        return {
            "action": "archived",
            "draft_id": draft_id,
            "archive_path": str(target),
            "deleted_path": str(source),
        }

    shutil.rmtree(source)
    return {"action": "deleted", "draft_id": draft_id, "deleted_path": str(source)}


def steps_for_instantiation(draft: dict[str, Any]) -> list[dict[str, Any]]:
    proposal = draft.get("proposal") or {}
    steps: list[dict[str, Any]] = []
    for step in proposal.get("steps") or []:
        item = dict(step)
        item["body"] = build_task_body(draft, step)
        steps.append(item)
    return steps


def build_task_body(draft: dict[str, Any], step: dict[str, Any]) -> str:
    proposal = draft.get("proposal") or {}
    lines = [
        "## 작업 목표",
        step.get("title") or step.get("key") or "Workflow step",
        "",
        "## 상세 지시",
        step.get("body") or "(상세 지시 없음)",
        "",
    ]
    criteria = step.get("acceptance_criteria") or []
    if criteria:
        lines.extend(["## Acceptance Criteria", *[f"- {item}" for item in criteria], ""])
    lines.extend(
        [
            "## Workflow Context",
            f"- Draft ID: {draft.get('draft_id')}",
            f"- Step: {step.get('key')}",
            f"- Depends on: {', '.join(step.get('depends_on') or []) or '(none)'}",
            f"- Workflow source: {PROMPT_WORKFLOW_SOURCE_ID}",
            "",
            "## 전체 Workflow 요약",
            proposal.get("summary") or "(요약 없음)",
            "",
            "## 전략",
            proposal.get("strategy") or "(전략 없음)",
            "",
            "## 원본 사용자 요청",
            draft.get("prompt") or "",
            "",
            "## 첨부 파일",
        ]
    )
    attachments = draft.get("attachments") or []
    if attachments:
        for attachment in attachments:
            excerpt = str(attachment.get("excerpt") or "").replace("\n", " ")
            lines.extend(
                [
                    f"- {attachment.get('filename')}",
                    f"  - 저장 경로: {attachment.get('path')}",
                    f"  - 발췌: {excerpt[:500]}",
                ]
            )
    else:
        lines.append("- 없음")
    lines.extend(
        [
            "",
            "## Worker Notes",
            "- parent task가 있으면 완료 결과를 먼저 확인한 뒤 진행하세요.",
            "- 작업 완료 시 검증 결과와 다음 단계에 필요한 handoff를 남기세요.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _sanitize_filename(name: str) -> str:
    cleaned = FILENAME_SAFE_RE.sub("_", Path(name).name).strip(" .")
    return cleaned[:120] or "attachment.txt"


def _dedupe_filename(name: str, used: set[str]) -> str:
    if name not in used:
        return name
    path = Path(name)
    stem = path.stem or "attachment"
    suffix = path.suffix
    index = 2
    while True:
        candidate = f"{stem}-{index}{suffix}"
        if candidate not in used:
            return candidate
        index += 1


def _excerpt(text: str) -> str:
    clean = text.strip()
    if len(clean) <= MAX_EXCERPT_CHARS:
        return clean
    return clean[:MAX_EXCERPT_CHARS] + f"… [truncated, {len(clean) - MAX_EXCERPT_CHARS} chars omitted]"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _normalize_skills(value: Any, errors: list[str], step_label: str) -> list[str]:
    skills = _string_list(value)
    for skill in skills:
        if "," in skill:
            errors.append(f"step {step_label} skill names cannot contain commas")
    return skills


def _has_cycle(graph: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)
