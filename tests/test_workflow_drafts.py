from __future__ import annotations

import json
from typing import Any


def _fake_proposal(
    title: str = "AI 설계: 결제 기능",
    *,
    applyable: bool = True,
    questions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "title": title,
        "summary": "결제 기능을 조사, 구현, 검증으로 나눕니다.",
        "strategy": "먼저 요구사항을 정리하고 구현 후 리뷰합니다.",
        "applyable": applyable,
        "questions": questions or [],
        "warnings": [],
        "steps": [
            {
                "key": "plan",
                "title": "기획: 결제 요구사항 정리",
                "body": "첨부된 요구사항을 읽고 구현 범위를 정리하세요.",
                "assignee": "dev_plan",
                "skills": ["writing-plans"],
                "priority": 5,
                "status": "ready",
                "depends_on": [],
                "acceptance_criteria": ["구현 범위가 정리됨"],
            },
            {
                "key": "implement",
                "title": "구현: 결제 API 추가",
                "body": "기획 결과를 바탕으로 테스트를 먼저 작성하고 구현하세요.",
                "assignee": "ghost_profile",
                "skills": ["test-driven-development"],
                "priority": 4,
                "status": "ready",
                "depends_on": ["plan"],
                "acceptance_criteria": ["테스트가 통과함"],
            },
        ],
    }


def _patch_profiles(monkeypatch):
    from kanban_webui.hermes_imports import kanban_db

    monkeypatch.setattr(kanban_db, "list_profiles_on_disk", lambda: ["default", "dev", "dev_plan"])


def _patch_planner(monkeypatch, seen: dict[str, Any] | None = None, proposal_factory=None):
    from kanban_webui import workflow_planner

    def fake_generate_workflow_proposal(**kwargs):
        if seen is not None:
            seen.update(kwargs)
        return proposal_factory() if proposal_factory else _fake_proposal()

    monkeypatch.setattr(workflow_planner, "generate_workflow_proposal", fake_generate_workflow_proposal)


def test_template_workflow_endpoints_are_deprecated(client):
    assert client.get("/api/workflows/templates").status_code == 410
    assert client.get("/api/workflows/templates/dev-plan-implement-review-v1").status_code == 410
    assert client.post(
        "/api/workflows/preview",
        json={"template_id": "dev-plan-implement-review-v1", "title": "x"},
    ).status_code == 410
    assert client.post(
        "/api/workflows/instantiate",
        json={"template_id": "dev-plan-implement-review-v1", "title": "x"},
    ).status_code == 410


def test_workflow_draft_creation_uses_ai_planner_profiles_and_attachments(client, monkeypatch):
    _patch_profiles(monkeypatch)
    seen: dict[str, Any] = {}
    _patch_planner(monkeypatch, seen)

    response = client.post(
        "/api/workflows/drafts?board=default",
        json={
            "prompt": "결제 기능을 여러 agent가 처리할 workflow로 설계해줘.",
            "max_steps": 8,
            "attachments": [
                {
                    "filename": "requirements.md",
                    "content_type": "text/markdown",
                    "content": "# 결제 요구사항\n- 카드 승인\n- 실패 재시도",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    draft = payload["draft"]
    assert payload["board"] == "default"
    assert draft["draft_id"].startswith("wfd_")
    assert draft["status"] == "draft"
    assert draft["planner_profile"] == "dev_plan"
    assert seen["planner_profile"] == "dev_plan"
    assert seen["max_steps"] == 8
    assert seen["attachments"][0]["filename"] == "requirements.md"

    assert draft["attachments"][0]["filename"] == "requirements.md"
    assert "카드 승인" in draft["attachments"][0]["excerpt"]
    assert draft["proposal"]["steps"][0]["status"] == "ready"
    assert draft["proposal"]["steps"][1]["status"] == "todo"
    assert draft["proposal"]["steps"][1]["assignee"] is None
    assert any("ghost_profile" in warning for warning in draft["validation"]["warnings"])
    assert [profile["name"] for profile in payload["profiles"]] == ["default", "dev", "dev_plan"]


def test_workflow_draft_apply_creates_tasks_links_and_locks_applied_draft(client, monkeypatch):
    _patch_profiles(monkeypatch)
    _patch_planner(monkeypatch)

    create = client.post(
        "/api/workflows/drafts?board=default",
        json={
            "prompt": "결제 기능 workflow를 만들어줘.",
            "attachments": [{"filename": "requirements.md", "content": "결제 요구사항 본문"}],
        },
    )
    assert create.status_code == 200, create.text
    draft_id = create.json()["draft"]["draft_id"]

    applied = client.post(
        f"/api/workflows/drafts/{draft_id}/instantiate?board=default",
        json={"instance_id": "wf_payment_ai"},
    )
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["created"] == 2
    assert result["existing"] == 0
    assert result["instance_id"] == "wf_payment_ai"
    assert result["tasks"][0]["step_key"] == "plan"
    assert result["tasks"][1]["step_key"] == "implement"
    assert result["links"] == [
        {
            "parent_step": "plan",
            "child_step": "implement",
            "parent_id": result["tasks"][0]["task_id"],
            "child_id": result["tasks"][1]["task_id"],
        }
    ]

    board = client.get("/api/board?board=default").json()
    by_step = {task["current_step_key"]: task for task in board["tasks"]}
    assert by_step["plan"]["status"] == "ready"
    assert by_step["plan"]["assignee"] == "dev_plan"
    assert by_step["plan"]["workflow_template_id"] == "prompt-generated-v1"
    assert by_step["implement"]["status"] == "todo"
    assert by_step["implement"]["assignee"] is None

    detail = client.get(f"/api/tasks/{by_step['plan']['id']}?board=default").json()
    assert "## 원본 사용자 요청" in detail["task"]["body"]
    assert "결제 기능 workflow" in detail["task"]["body"]
    assert "requirements.md" in detail["task"]["body"]

    loaded = client.get(f"/api/workflows/drafts/{draft_id}?board=default")
    assert loaded.status_code == 200
    assert loaded.json()["draft"]["status"] == "applied"
    assert loaded.json()["draft"]["applied_instance_id"] == "wf_payment_ai"

    revise = client.post(
        f"/api/workflows/drafts/{draft_id}/revise?board=default",
        json={"revision_prompt": "구현 단계를 둘로 나눠줘."},
    )
    assert revise.status_code == 409

    second_apply = client.post(
        f"/api/workflows/drafts/{draft_id}/instantiate?board=default",
        json={"instance_id": "wf_payment_ai"},
    )
    assert second_apply.status_code == 409


def test_workflow_draft_apply_preserves_explicit_root_todo_and_triage_statuses(client, monkeypatch):
    _patch_profiles(monkeypatch)

    def proposal_with_root_todo_and_triage():
        proposal = _fake_proposal()
        proposal["steps"][0]["status"] = "todo"
        proposal["steps"].append(
            {
                "key": "triage",
                "title": "분류: 결제 요청 검토",
                "body": "요청을 먼저 triage 하세요.",
                "assignee": "dev_plan",
                "skills": [],
                "priority": 3,
                "status": "triage",
                "depends_on": [],
                "acceptance_criteria": ["분류가 완료됨"],
            }
        )
        return proposal

    _patch_planner(monkeypatch, proposal_factory=proposal_with_root_todo_and_triage)

    create = client.post(
        "/api/workflows/drafts?board=default",
        json={"prompt": "root todo workflow를 만들어줘."},
    )
    assert create.status_code == 200, create.text
    draft = create.json()["draft"]
    assert draft["proposal"]["steps"][0]["status"] == "todo"
    assert draft["proposal"]["steps"][1]["status"] == "todo"
    assert draft["proposal"]["steps"][2]["status"] == "triage"

    applied = client.post(
        f"/api/workflows/drafts/{draft['draft_id']}/instantiate?board=default",
        json={"instance_id": "wf_root_todo"},
    )
    assert applied.status_code == 200, applied.text
    result = applied.json()
    result_by_step = {task["step_key"]: task for task in result["tasks"]}
    assert result_by_step["plan"]["status"] == "todo"
    assert result_by_step["implement"]["status"] == "todo"
    assert result_by_step["triage"]["status"] == "triage"

    board = client.get("/api/board?board=default").json()
    by_step = {task["current_step_key"]: task for task in board["tasks"]}
    assert by_step["plan"]["status"] == "todo"
    assert by_step["implement"]["status"] == "todo"
    assert by_step["triage"]["status"] == "triage"


def test_workflow_draft_rejects_wrong_board_access_and_apply(client, monkeypatch):
    _patch_profiles(monkeypatch)
    _patch_planner(monkeypatch)

    created_board = client.post('/api/boards', json={'slug': 'other', 'name': 'Other'})
    assert created_board.status_code == 200, created_board.text
    create = client.post(
        "/api/workflows/drafts?board=default",
        json={"prompt": "default board 전용 workflow"},
    )
    assert create.status_code == 200, create.text
    draft_id = create.json()["draft"]["draft_id"]

    wrong_get = client.get(f"/api/workflows/drafts/{draft_id}?board=other")
    assert wrong_get.status_code == 404

    wrong_revise = client.post(
        f"/api/workflows/drafts/{draft_id}/revise?board=other",
        json={"revision_prompt": "다른 보드에서 수정하면 안 됨"},
    )
    assert wrong_revise.status_code == 404

    wrong_apply = client.post(
        f"/api/workflows/drafts/{draft_id}/instantiate?board=other",
        json={"instance_id": "wf_wrong_board"},
    )
    assert wrong_apply.status_code == 404
    other_board = client.get("/api/board?board=other")
    assert other_board.status_code == 200, other_board.text
    assert other_board.json()["tasks"] == []


def test_workflow_draft_cannot_apply_when_proposal_is_not_applyable(client, monkeypatch):
    _patch_profiles(monkeypatch)
    from kanban_webui import workflow_planner

    def blocked_proposal(**_kwargs):
        return _fake_proposal(applyable=False, questions=["먼저 범위를 확인해야 합니다."])

    monkeypatch.setattr(workflow_planner, "generate_workflow_proposal", blocked_proposal)

    create = client.post(
        "/api/workflows/drafts?board=default",
        json={"prompt": "질문이 남은 workflow"},
    )
    assert create.status_code == 200, create.text
    draft = create.json()["draft"]
    assert draft["proposal"]["applyable"] is False
    assert draft["proposal"]["questions"] == ["먼저 범위를 확인해야 합니다."]

    applied = client.post(
        f"/api/workflows/drafts/{draft['draft_id']}/instantiate?board=default",
        json={"instance_id": "wf_blocked"},
    )
    assert applied.status_code == 409
    assert "not applyable" in applied.text
    board = client.get("/api/board?board=default").json()
    assert board["tasks"] == []


def test_workflow_draft_revision_replaces_proposal_before_apply(client, monkeypatch):
    _patch_profiles(monkeypatch)
    from kanban_webui import workflow_planner

    calls: list[dict[str, Any]] = []

    def fake_generate_workflow_proposal(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _fake_proposal("초안")
        proposal = _fake_proposal("수정안")
        proposal["steps"][0]["title"] = "기획: 수정된 요구사항 정리"
        return proposal

    monkeypatch.setattr(workflow_planner, "generate_workflow_proposal", fake_generate_workflow_proposal)

    create = client.post(
        "/api/workflows/drafts?board=default",
        json={"prompt": "처음 요청"},
    )
    assert create.status_code == 200, create.text
    draft_id = create.json()["draft"]["draft_id"]

    revise = client.post(
        f"/api/workflows/drafts/{draft_id}/revise?board=default",
        json={"revision_prompt": "첫 단계 제목을 더 명확하게 바꿔줘."},
    )
    assert revise.status_code == 200, revise.text
    draft = revise.json()["draft"]
    assert draft["revision"] == 2
    assert draft["proposal"]["title"] == "수정안"
    assert draft["proposal"]["steps"][0]["title"] == "기획: 수정된 요구사항 정리"
    assert calls[1]["previous_proposal"]["title"] == "초안"
    assert calls[1]["revision_prompt"] == "첫 단계 제목을 더 명확하게 바꿔줘."


def test_workflow_draft_rejects_invalid_ai_proposal(client, monkeypatch):
    _patch_profiles(monkeypatch)
    from kanban_webui import workflow_planner

    def invalid_proposal(**_kwargs):
        return {
            "schema_version": 1,
            "title": "broken",
            "summary": "broken",
            "steps": [
                {"key": "a", "title": "A", "depends_on": ["b"]},
                {"key": "b", "title": "B", "depends_on": ["a"]},
            ],
        }

    monkeypatch.setattr(workflow_planner, "generate_workflow_proposal", invalid_proposal)

    response = client.post(
        "/api/workflows/drafts?board=default",
        json={"prompt": "cycle을 만들지 말아줘."},
    )
    assert response.status_code == 422
    assert "cycle" in response.text or "순환" in response.text


def test_workflow_draft_list_is_board_scoped_searchable_and_lightweight(client, monkeypatch):
    _patch_profiles(monkeypatch)
    from kanban_webui import workflow_drafts
    from kanban_webui.config import get_settings

    proposals = [
        _fake_proposal("Default newest draft"),
        _fake_proposal("Default applied rollout"),
        _fake_proposal("Other board draft"),
    ]
    _patch_planner(monkeypatch, proposal_factory=lambda: proposals.pop(0))

    created_board = client.post('/api/boards', json={'slug': 'other', 'name': 'Other'})
    assert created_board.status_code == 200, created_board.text

    newest = client.post(
        "/api/workflows/drafts?board=default",
        json={
            "prompt": "newest draft",
            "attachments": [
                {"filename": "secret.txt", "content": "large attachment body must not leak"}
            ],
        },
    )
    assert newest.status_code == 200, newest.text
    applied = client.post("/api/workflows/drafts?board=default", json={"prompt": "applied draft"})
    assert applied.status_code == 200, applied.text
    other = client.post("/api/workflows/drafts?board=other", json={"prompt": "other draft"})
    assert other.status_code == 200, other.text

    settings = get_settings()
    newest_draft = newest.json()["draft"]
    applied_draft = applied.json()["draft"]
    other_draft = other.json()["draft"]
    newest_draft.update({"created_at": 300, "updated_at": 300})
    workflow_drafts.save_draft(settings, newest_draft)
    applied_draft.update(
        {
            "status": "applied",
            "created_at": 200,
            "updated_at": 250,
            "applied_at": 250,
            "applied_instance_id": "wf_applied_list",
        }
    )
    workflow_drafts.save_draft(settings, applied_draft)
    other_draft.update({"created_at": 400, "updated_at": 400})
    workflow_drafts.save_draft(settings, other_draft)

    listed = client.get("/api/workflows/drafts?board=default")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["board"] == "default"
    assert payload["count"] == 2
    summaries = payload["drafts"]
    assert [item["draft_id"] for item in summaries] == [
        newest_draft["draft_id"],
        applied_draft["draft_id"],
    ]
    assert {item["board"] for item in summaries} == {"default"}
    assert {item["status"] for item in summaries} == {"draft", "applied"}
    applied_summary = next(item for item in summaries if item["status"] == "applied")
    assert applied_summary["applied_at"] == 250
    assert applied_summary["applied_instance_id"] == "wf_applied_list"
    assert summaries[0]["proposal"] == {
        "title": "Default newest draft",
        "summary": "결제 기능을 조사, 구현, 검증으로 나눕니다.",
    }
    assert summaries[0]["planner_profile"] == "dev_plan"
    assert summaries[0]["attachment_count"] == 1
    assert "attachments" not in summaries[0]
    assert "steps" not in summaries[0]["proposal"]
    assert "large attachment body" not in json.dumps(payload, ensure_ascii=False)

    searched = client.get("/api/workflows/drafts?board=default&q=rollout")
    assert searched.status_code == 200, searched.text
    assert [item["draft_id"] for item in searched.json()["drafts"]] == [applied_draft["draft_id"]]

    other_listed = client.get("/api/workflows/drafts?board=other")
    assert other_listed.status_code == 200, other_listed.text
    assert [item["draft_id"] for item in other_listed.json()["drafts"]] == [other_draft["draft_id"]]


def test_workflow_draft_list_skips_invalid_draft_files(client, monkeypatch):
    _patch_profiles(monkeypatch)
    _patch_planner(monkeypatch)
    from kanban_webui import workflow_drafts
    from kanban_webui.config import get_settings

    create = client.post("/api/workflows/drafts?board=default", json={"prompt": "valid draft"})
    assert create.status_code == 200, create.text
    draft_id = create.json()["draft"]["draft_id"]

    bad_dir = workflow_drafts.drafts_root(get_settings()) / "wfd_broken"
    bad_dir.mkdir(parents=True)
    (bad_dir / "draft.json").write_text("{not json", encoding="utf-8")

    response = client.get("/api/workflows/drafts?board=default")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["draft_id"] for item in payload["drafts"]] == [draft_id]
    assert payload["invalid_drafts"]
    assert payload["invalid_drafts"][0]["draft_id"] == "wfd_broken"
