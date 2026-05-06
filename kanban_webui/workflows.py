"""Workflow template helpers for KanbanWebUI.

MVP scope: instantiate a workflow template as a DAG of normal Hermes Kanban
Tasks.  The Hermes kanban_db remains the source of truth; this module only
validates templates, renders step task fields, and writes the forward-compatible
workflow columns already present on task rows.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from copy import deepcopy
from typing import Any, Iterable, Optional

from .hermes_imports import kanban_db

WORKFLOW_PREFIX = "workflow:"
INSTANCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TEMPLATE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
STEP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ALLOWED_STEP_STATUSES = {"ready", "todo", "triage"}

BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "dev-plan-implement-review-v1",
        "name": "Plan → Implement → Review",
        "description": "기획, 구현, 리뷰를 순서대로 실행하는 개발 workflow",
        "version": 1,
        "entry_step": "plan",
        "steps": [
            {
                "key": "plan",
                "title": "기획: {title}",
                "body": "요청:\n{body}\n\n상세 구현 계획을 작성하고 구현 범위와 검증 방법을 정리하세요.",
                "assignee": "dev_plan",
                "skills": ["writing-plans"],
                "priority": 5,
                "status": "ready",
                "depends_on": [],
            },
            {
                "key": "implement",
                "title": "구현: {title}",
                "body": "상위 기획 task의 결과를 바탕으로 테스트를 먼저 작성한 뒤 구현하세요.",
                "assignee": "dev",
                "skills": ["test-driven-development"],
                "priority": 4,
                "status": "todo",
                "depends_on": ["plan"],
            },
            {
                "key": "review",
                "title": "리뷰: {title}",
                "body": "상위 구현 task의 변경사항을 리뷰하고 필요한 수정사항과 검증 결과를 정리하세요.",
                "assignee": "dev_plan",
                "skills": ["requesting-code-review"],
                "priority": 3,
                "status": "todo",
                "depends_on": ["implement"],
            },
        ],
    }
]


def list_templates() -> list[dict[str, Any]]:
    """Return validated built-in workflow templates for API consumers."""
    templates = []
    for template in BUILTIN_TEMPLATES:
        errors = validate_template(template)
        if errors:
            item = _template_public(template)
            item["errors"] = errors
            templates.append(item)
        else:
            templates.append(_template_public(template))
    return templates


def get_template(template_id: str) -> dict[str, Any]:
    for template in BUILTIN_TEMPLATES:
        if template["id"] == template_id:
            errors = validate_template(template)
            if errors:
                raise ValueError("; ".join(errors))
            return deepcopy(template)
    raise KeyError(template_id)


def validate_template(template: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    template_id = str(template.get("id") or "")
    if not TEMPLATE_RE.match(template_id):
        errors.append("template id must match [a-z0-9][a-z0-9._-]*")

    steps = template.get("steps") or []
    if not isinstance(steps, list) or not steps:
        errors.append("template must define at least one step")
        return errors

    keys: list[str] = []
    seen: set[str] = set()
    for step in steps:
        key = str(step.get("key") or "")
        if not STEP_RE.match(key):
            errors.append(f"invalid step key: {key!r}")
        if key in seen:
            errors.append(f"duplicate step key: {key}")
        seen.add(key)
        keys.append(key)

        title = str(step.get("title") or "")
        if not title.strip():
            errors.append(f"step {key or '?'} title is required")
        status = str(step.get("status") or "ready")
        if status not in ALLOWED_STEP_STATUSES:
            errors.append(f"step {key or '?'} status must be one of {sorted(ALLOWED_STEP_STATUSES)}")
        for skill in step.get("skills") or []:
            if "," in str(skill):
                errors.append(f"step {key or '?'} skill names cannot contain commas")

    known = set(keys)
    entry = str(template.get("entry_step") or keys[0])
    if entry not in known:
        errors.append(f"entry_step {entry!r} does not exist")

    graph = {key: [] for key in keys}
    for step in steps:
        key = str(step.get("key") or "")
        for parent in step.get("depends_on") or []:
            parent_key = str(parent)
            if parent_key not in known:
                errors.append(f"step {key} depends on unknown step {parent_key}")
            else:
                graph[parent_key].append(key)

    if _has_cycle(graph):
        errors.append("workflow step graph cannot contain cycles")
    return errors


def preview_workflow(
    template_id: str,
    *,
    title: str,
    body: Optional[str] = None,
    assignee_overrides: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    template = get_template(template_id)
    steps = _render_steps(template, title=title, body=body, assignee_overrides=assignee_overrides)
    return {
        "template_id": template["id"],
        "template_name": template.get("name") or template["id"],
        "instance_id": "preview",
        "steps": steps,
        "links": _preview_links(steps),
    }


def instantiate_workflow(
    conn,
    template_id: str,
    *,
    title: str,
    body: Optional[str] = None,
    instance_id: Optional[str] = None,
    assignee_overrides: Optional[dict[str, str]] = None,
    created_by: Optional[str] = "kanban-webui",
    workspace_kind: str = "scratch",
    workspace_path: Optional[str] = None,
    tenant: Optional[str] = None,
    priority_offset: int = 0,
) -> dict[str, Any]:
    template = get_template(template_id)
    if not title or not title.strip():
        raise ValueError("workflow title is required")
    instance = normalize_instance_id(instance_id)
    preview = preview_workflow(
        template_id,
        title=title,
        body=body,
        assignee_overrides=assignee_overrides,
    )

    step_task_ids: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    created_count = 0
    existing_count = 0

    for step in preview["steps"]:
        step_key = step["step_key"]
        idem = idempotency_key(instance, step_key)
        existing_id = task_id_for_idempotency(conn, idem)
        parents = [step_task_ids[parent_key] for parent_key in step.get("depends_on") or []]
        if existing_id:
            task_id = existing_id
            existing_count += 1
        else:
            task_id = kanban_db.create_task(
                conn,
                title=step["title"],
                body=step.get("body"),
                assignee=step.get("assignee"),
                created_by=created_by,
                workspace_kind=workspace_kind,
                workspace_path=workspace_path,
                tenant=tenant,
                priority=int(step.get("priority") or 0) + int(priority_offset or 0),
                parents=parents,
                triage=step.get("status") == "triage",
                idempotency_key=idem,
                max_runtime_seconds=step.get("max_runtime_seconds"),
                skills=step.get("skills") or None,
            )
            created_count += 1
        step_task_ids[step_key] = task_id
        attach_workflow_fields(conn, task_id, template["id"], step_key)
        task = kanban_db.get_task(conn, task_id)
        results.append(
            {
                "step_key": step_key,
                "task_id": task_id,
                "title": task.title if task else step["title"],
                "status": task.status if task else step["status"],
                "assignee": task.assignee if task else step.get("assignee"),
                "idempotency_key": idem,
                "existing": bool(existing_id),
            }
        )

    return {
        "ok": True,
        "template_id": template["id"],
        "template_name": template.get("name") or template["id"],
        "instance_id": instance,
        "created": created_count,
        "existing": existing_count,
        "tasks": results,
        "links": _instantiated_links(preview["links"], step_task_ids),
    }


def instantiate_steps_workflow(
    conn,
    *,
    source_id: str,
    source_name: str,
    steps: list[dict[str, Any]],
    instance_id: Optional[str] = None,
    created_by: Optional[str] = "kanban-webui",
    workspace_kind: str = "scratch",
    workspace_path: Optional[str] = None,
    tenant: Optional[str] = None,
    priority_offset: int = 0,
) -> dict[str, Any]:
    """Instantiate an already-validated workflow proposal as linked Kanban tasks."""
    instance = normalize_instance_id(instance_id)
    ordered_steps = _topological_steps(steps)
    step_task_ids: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    created_count = 0
    existing_count = 0

    for step in ordered_steps:
        step_key = str(step.get("step_key") or step.get("key") or "")
        if not step_key:
            raise ValueError("workflow step key is required")
        idem = idempotency_key(instance, step_key)
        existing_id = task_id_for_idempotency(conn, idem)
        parent_keys = list(step.get("depends_on") or [])
        parents = [step_task_ids[parent_key] for parent_key in parent_keys]
        if existing_id:
            task_id = existing_id
            existing_count += 1
        else:
            task_id = kanban_db.create_task(
                conn,
                title=str(step.get("title") or step_key),
                body=step.get("body"),
                assignee=step.get("assignee"),
                created_by=created_by,
                workspace_kind=workspace_kind,
                workspace_path=workspace_path,
                tenant=tenant,
                priority=int(step.get("priority") or 0) + int(priority_offset or 0),
                parents=parents,
                triage=step.get("status") == "triage",
                idempotency_key=idem,
                max_runtime_seconds=step.get("max_runtime_seconds"),
                skills=step.get("skills") or None,
            )
            created_count += 1
        step_task_ids[step_key] = task_id
        attach_workflow_fields(conn, task_id, source_id, step_key)
        task = kanban_db.get_task(conn, task_id)
        results.append(
            {
                "step_key": step_key,
                "task_id": task_id,
                "title": task.title if task else str(step.get("title") or step_key),
                "status": task.status if task else str(step.get("status") or "ready"),
                "assignee": task.assignee if task else step.get("assignee"),
                "idempotency_key": idem,
                "existing": bool(existing_id),
            }
        )

    preview_links = _preview_links([
        {"step_key": str(step.get("step_key") or step.get("key")), "depends_on": list(step.get("depends_on") or [])}
        for step in ordered_steps
    ])
    for link in preview_links:
        kanban_db.link_tasks(conn, step_task_ids[link["parent_step"]], step_task_ids[link["child_step"]])

    return {
        "ok": True,
        "template_id": source_id,
        "template_name": source_name,
        "instance_id": instance,
        "created": created_count,
        "existing": existing_count,
        "tasks": results,
        "links": _instantiated_links(preview_links, step_task_ids),
    }


def workflow_instance(conn, instance_id: str) -> Optional[dict[str, Any]]:
    instance = validate_instance_id(instance_id)
    prefix = f"{WORKFLOW_PREFIX}{instance}:"
    rows = conn.execute(
        "SELECT * FROM tasks WHERE idempotency_key LIKE ? AND status != 'archived' ORDER BY created_at ASC, id ASC",
        (prefix + "%",),
    ).fetchall()
    if not rows:
        return None
    tasks = [kanban_db.Task.from_row(row) for row in rows]
    template_id = next((task.workflow_template_id for task in tasks if task.workflow_template_id), None)
    template_order = _step_order(template_id)
    task_ids = [task.id for task in tasks]
    links = _links_between_tasks(conn, task_ids)
    if template_order:
        tasks.sort(key=lambda task: (template_order.get(task.current_step_key or "", 10_000), task.created_at, task.id))
    else:
        dependency_order = _dependency_task_order(task_ids, links)
        tasks.sort(key=lambda task: (dependency_order.get(task.id, 10_000), task.created_at, task.id))
    done = sum(1 for task in tasks if task.status == "done")
    return {
        "instance_id": instance,
        "template_id": template_id,
        "tasks": tasks,
        "links": links,
        "progress": {"done": done, "total": len(tasks)},
    }


def idempotency_key(instance_id: str, step_key: str) -> str:
    return f"{WORKFLOW_PREFIX}{instance_id}:{step_key}"


def parse_instance_id(value: Optional[str]) -> Optional[str]:
    if not value or not value.startswith(WORKFLOW_PREFIX):
        return None
    parts = value.split(":", 2)
    if len(parts) < 3:
        return None
    return parts[1] or None


def normalize_instance_id(value: Optional[str]) -> str:
    if value is None or not str(value).strip():
        return f"wf_{int(time.time())}_{secrets.token_hex(3)}"
    return validate_instance_id(str(value).strip())


def validate_instance_id(value: str) -> str:
    if not INSTANCE_RE.match(value):
        raise ValueError("workflow instance_id must match [A-Za-z0-9][A-Za-z0-9._-]*")
    return value


def task_id_for_idempotency(conn, key: str) -> Optional[str]:
    row = conn.execute(
        "SELECT id FROM tasks WHERE idempotency_key = ? AND status != 'archived' ORDER BY created_at DESC LIMIT 1",
        (key,),
    ).fetchone()
    return row["id"] if row else None


def attach_workflow_fields(conn, task_id: str, template_id: str, step_key: str) -> None:
    with kanban_db.write_txn(conn):
        conn.execute(
            "UPDATE tasks SET workflow_template_id = ?, current_step_key = ? WHERE id = ?",
            (template_id, step_key, task_id),
        )
        conn.execute(
            "INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
            (
                task_id,
                "workflow_attached",
                json.dumps({"template_id": template_id, "step_key": step_key}, ensure_ascii=False),
                int(time.time()),
            ),
        )


def _template_public(template: dict[str, Any]) -> dict[str, Any]:
    item = deepcopy(template)
    item["step_count"] = len(item.get("steps") or [])
    return item


def _render_steps(
    template: dict[str, Any],
    *,
    title: str,
    body: Optional[str],
    assignee_overrides: Optional[dict[str, str]],
) -> list[dict[str, Any]]:
    values = {"title": title.strip(), "body": body or ""}
    overrides = assignee_overrides or {}
    rendered: list[dict[str, Any]] = []
    for step in template["steps"]:
        key = step["key"]
        depends_on = list(step.get("depends_on") or [])
        status = _preview_status(step, depends_on)
        rendered.append(
            {
                "step_key": key,
                "title": _render_template_text(step.get("title") or "", values),
                "body": _render_template_text(step.get("body") or "", values),
                "assignee": overrides.get(key, step.get("assignee")),
                "skills": list(step.get("skills") or []),
                "priority": int(step.get("priority") or 0),
                "status": status,
                "depends_on": depends_on,
                "max_runtime_seconds": step.get("max_runtime_seconds"),
            }
        )
    return rendered


def _render_template_text(template: str, values: dict[str, str]) -> str:
    try:
        return template.format(**values)
    except Exception:
        return template


def _preview_status(step: dict[str, Any], depends_on: Iterable[str]) -> str:
    requested = str(step.get("status") or "ready")
    if requested == "triage":
        return "triage"
    if list(depends_on):
        return "todo"
    return requested


def _preview_links(steps: list[dict[str, Any]]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for step in steps:
        for parent in step.get("depends_on") or []:
            links.append({"parent_step": parent, "child_step": step["step_key"]})
    return links


def _instantiated_links(links: list[dict[str, str]], step_task_ids: dict[str, str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for link in links:
        parent_step = link["parent_step"]
        child_step = link["child_step"]
        out.append(
            {
                "parent_step": parent_step,
                "child_step": child_step,
                "parent_id": step_task_ids[parent_step],
                "child_id": step_task_ids[child_step],
            }
        )
    return out


def _topological_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {str(step.get("step_key") or step.get("key")): step for step in steps}
    ordered: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visited:
            return
        if key in visiting:
            raise ValueError("workflow step graph cannot contain cycles")
        if key not in by_key:
            raise ValueError(f"workflow step depends on unknown step {key}")
        visiting.add(key)
        for parent in by_key[key].get("depends_on") or []:
            visit(str(parent))
        visiting.remove(key)
        visited.add(key)
        ordered.append(by_key[key])

    for step in steps:
        visit(str(step.get("step_key") or step.get("key")))
    return ordered


def _links_between_tasks(conn, task_ids: list[str]) -> list[dict[str, str]]:
    if not task_ids:
        return []
    placeholders = ",".join("?" * len(task_ids))
    rows = conn.execute(
        f"""
        SELECT l.parent_id, l.child_id,
               p.current_step_key AS parent_step,
               c.current_step_key AS child_step
          FROM task_links l
          JOIN tasks p ON p.id = l.parent_id
          JOIN tasks c ON c.id = l.child_id
         WHERE l.parent_id IN ({placeholders})
           AND l.child_id IN ({placeholders})
        """,
        tuple(task_ids) + tuple(task_ids),
    ).fetchall()
    order = {task_id: index for index, task_id in enumerate(task_ids)}
    sorted_rows = sorted(rows, key=lambda row: (order.get(row["parent_id"], 10_000), order.get(row["child_id"], 10_000)))
    return [
        {
            "parent_step": row["parent_step"],
            "child_step": row["child_step"],
            "parent_id": row["parent_id"],
            "child_id": row["child_id"],
        }
        for row in sorted_rows
    ]


def _dependency_task_order(task_ids: list[str], links: list[dict[str, str]]) -> dict[str, int]:
    children: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    parents: dict[str, set[str]] = {task_id: set() for task_id in task_ids}
    for link in links:
        parent_id = link["parent_id"]
        child_id = link["child_id"]
        if parent_id in children and child_id in parents:
            children[parent_id].append(child_id)
            parents[child_id].add(parent_id)
    ready = [task_id for task_id in task_ids if not parents[task_id]]
    ordered: list[str] = []
    while ready:
        task_id = ready.pop(0)
        if task_id in ordered:
            continue
        ordered.append(task_id)
        for child_id in children.get(task_id, []):
            parents[child_id].discard(task_id)
            if not parents[child_id]:
                ready.append(child_id)
    for task_id in task_ids:
        if task_id not in ordered:
            ordered.append(task_id)
    return {task_id: index for index, task_id in enumerate(ordered)}


def _step_order(template_id: Optional[str]) -> dict[str, int]:
    if not template_id:
        return {}
    try:
        template = get_template(template_id)
    except (KeyError, ValueError):
        return {}
    return {step["key"]: index for index, step in enumerate(template.get("steps") or [])}


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
