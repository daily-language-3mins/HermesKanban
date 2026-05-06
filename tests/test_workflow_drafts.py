from __future__ import annotations

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


def _patch_planner(monkeypatch, seen: dict[str, Any] | None = None):
    from kanban_webui import workflow_planner

    def fake_generate_workflow_proposal(**kwargs):
        if seen is not None:
            seen.update(kwargs)
        return _fake_proposal()

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
