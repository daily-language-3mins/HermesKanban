# AI 프롬프트 기반 Workflow Designer 구현 계획

작성일: 2026-05-06
대상 repo: HermesKanban checkout root

## 0. 한 줄 요약

기존 `템플릿 기반 Workflow 생성`은 **유지하지 않는다.** 수동 task 생성 기능은 그대로 두고, workflow 생성 경로는 `AI 프롬프트 기반 Workflow Designer`로 대체한다.

```text
프롬프트 + 첨부파일
→ AI가 workflow draft(JSON DAG)를 설계
→ UI에서 단계/의존성/담당 프로필/주의사항을 제시
→ 사용자가 수정 프롬프트로 revision 반복
→ 최종 승인 시 기존 Kanban task + task_links로 적용
```

핵심 원칙:

- AI는 **task를 바로 만들지 않는다.** 먼저 `draft`만 만든다.
- 사용자가 `적용`을 눌러야 실제 `tasks`, `task_links`가 생성된다.
- `템플릿 선택/미리보기/템플릿 적용` UI와 API는 user-facing 기능에서 제거한다.
- 기존 Kanban 실행 모델을 그대로 쓴다.
  - dependency 없는 root step: `ready`
  - dependency 있는 step: `todo`
  - parent 완료 후 기존 promotion/dispatcher가 처리
- MVP는 새 DB migration 없이 `state_dir`의 JSON draft 파일과 기존 Kanban DB만 사용한다.
- 첨부파일은 MVP 필수 범위다.
  - 파일 업로드/저장/worker task body 참조는 MVP에 포함한다.
  - planner가 읽는 본문 추출은 text-like 파일과 PDF text layer를 우선 지원한다.
  - 이미지 OCR/음성/복잡한 binary 의미 해석은 후속 기능으로 분리한다.
- AI planner 기능은 기본 활성화한다. 단 운영자가 env로 끌 수는 있어야 한다.

## 1. 현재 코드 기준 확인 사항

확인한 현재 구조와 이번 변경 방향:

- Backend workflow helper:
  - `kanban_webui/workflows.py`
  - 현재 built-in template registry, preview, instantiate, cycle validation 보유
  - 변경 방향: template registry 중심 구조를 user-facing 기능에서 제거하고, `WorkflowProposal.steps`를 직접 instantiate하는 generic helper로 축소/전환
- API route:
  - `kanban_webui/kanban_api.py`
  - 현재 template workflow endpoint:
    - `GET /api/workflows/templates`
    - `GET /api/workflows/templates/{template_id}`
    - `POST /api/workflows/preview`
    - `POST /api/workflows/instantiate`
    - `GET /api/workflows/instances/{instance_id}`
  - 변경 방향: template endpoint는 제거하거나 deprecated 404/410 처리하고, draft endpoint만 남김
- Frontend:
  - `static/forms.js`: 현재 workflow dialog/preview/instantiate 담당
  - `static/api.js`: workflow API client 존재
  - `static/index.html`: `Workflow 생성` modal 존재
  - `static/style.css`, `static/i18n.js`: workflow UI 스타일/문구 존재
  - 변경 방향: template select/preview controls 제거, AI prompt designer 단일 화면으로 교체
- Test:
  - `tests/test_workflows.py`
  - `tests/test_static_smoke.py`
  - 변경 방향: template workflow contract tests는 제거/수정하고 prompt draft/apply contract tests로 대체
- 상태 디렉터리:
  - `kanban_webui/config.py`에 `Settings.state_dir`
  - 기본값: `~/.hermes/kanban-webui`
  - draft/attachment 저장 위치로 재사용
- 의존성:
  - 현재 `fastapi`, `uvicorn`, `pydantic`
  - multipart upload를 위해 `python-multipart` 추가 필요
  - PDF text layer 추출을 MVP에 넣으면 `pypdf` 추가 검토
- Hermes CLI:
  - `hermes chat -Q -q ...` 사용 가능
  - `--toolsets none`을 주면 planner agent가 도구 없이 JSON 설계만 하게 만들 수 있음
  - `--max-turns 1`, `--ignore-rules`, `--source kanban-webui-planner` 사용 권장
- Agent profile 주의:
  - 사용자/설치 환경마다 profile 이름이 다르다.
  - `dev_plan`은 이 환경의 추천 기본값이지만, 코드에서 존재를 가정하면 안 된다.
  - UI/API는 board의 `known_assignees`/on-disk profiles를 기준으로 planner/task assignee 후보를 동적으로 구성해야 한다.

## 2. MVP 범위

### 포함

1. 프롬프트 입력으로 workflow draft 생성
2. 첨부파일 업로드/저장/참조를 MVP에 포함
   - text/markdown/json/yaml/csv/source code는 본문 추출
   - PDF는 text layer 추출을 우선 지원하거나, 의존성 부담이 크면 저장+warning으로 시작
   - image/OCR/음성 의미 해석은 후속
3. AI가 생성한 단계/의존성/담당 프로필/우선순위/본문/검증 기준 표시
4. 수정 프롬프트로 draft revision 생성
5. 최종 승인 시 실제 Kanban task 생성
6. parent/child dependency를 기존 `task_links`로 연결
7. idempotency key로 중복 적용 방지
8. AI planner 기능 기본 활성화
9. 사용자/설치 환경별 agent profile 차이를 반영한 동적 profile 선택
10. 기존 template workflow 생성 UI/API 제거 또는 명시적 deprecated 처리
11. UI 다크모드/라이트모드 대응
12. Backend + frontend + browser smoke 테스트
13. 문서화: README 또는 `docs/WORKFLOWS.md`/`docs/TROUBLESHOOTING.md`

### 제외 / 후속

1. 기존 템플릿 기반 Workflow 생성의 유지/호환성 보장
2. 드래그앤드롭으로 workflow DAG 직접 편집
3. AI가 자동으로 task를 dispatch하거나 실행
4. 다중 사용자/권한별 draft 격리
   - MVP는 single WebUI instance 기준
   - 다만 profile 목록/기본값은 사용자 환경마다 달라지는 것을 반영
5. workflow instance 전용 DB table
6. 장시간 background generation queue
7. 실시간 streaming generation
8. 이미지 OCR/음성/복잡한 binary attachment 의미 해석

## 3. 사용자 경험 설계

### 3.1 진입점

기존 `Workflow 생성` 버튼은 `AI Workflow 설계` 또는 `Workflow 설계`로 의미를 바꾸고, template 선택 UI는 제거한다.

```text
AI Workflow 설계
```

수동 task 생성 기능은 기존 quick create/bulk create/수동 노드 생성 흐름을 유지한다. 제거 대상은 **템플릿 기반 workflow 생성 경로**뿐이다.

추천 UI:

```text
[AI Workflow 설계]
```

버튼을 누르면 prompt 기반 designer modal이 바로 열린다. 탭 구조는 만들지 않는다.

### 3.2 프롬프트 기반 생성 화면

필드:

```text
요청 프롬프트 textarea
첨부파일 input multiple      MVP 필수
Planner 프로필 select       기본값은 동적 결정: env override → dev_plan 존재 시 → default 존재 시 → 첫 on-disk profile
Instance ID input          선택 사항
최대 단계 수 input          기본 8, 최대 20
Workspace kind/path        기존 task 생성 옵션과 동일하게 재사용 가능하면 포함
```

버튼:

```text
[설계 생성]
```

생성 중 상태:

```text
AI가 workflow를 설계 중입니다… 30~180초 걸릴 수 있습니다.
```

### 3.3 Workflow 제시 화면

AI 결과를 아래처럼 보여준다.

```text
요약
- 목표: ...
- 전략: ...
- 주의사항: ...

단계
1. 조사: 요구사항/기존 코드 파악
   담당 프로필: research 또는 dev_plan
   상태: ready
   의존성: 없음
   검증 기준: ...

2. 구현: backend API 추가
   담당 프로필: dev
   상태: todo
   의존성: 조사
   검증 기준: pytest ...

3. 리뷰: 코드 리뷰 및 QA
   담당 프로필: dev_plan
   상태: todo
   의존성: 구현
```

추가 패널:

```text
질문 / 사용자 결정 필요
- 첨부파일 중 일부는 본문 추출이 제한됩니다. 저장 경로/파일명만 workflow에 참조할까요?
- deployment는 이번 workflow에 포함할까요?

위험 / 경고
- profile `media`가 현재 보드에는 있지만 작업 내용과 맞지 않습니다.
- root task가 3개라 병렬 실행됩니다.
```

버튼:

```text
[수정 요청]
[이 workflow 적용]
[취소]
```

### 3.4 Revision 흐름

수정 요청 입력 예:

```text
리뷰 전에 browser QA 단계를 추가하고, 구현은 backend와 frontend로 나눠줘.
```

Backend는 기존 proposal 전체와 수정 프롬프트를 함께 AI에 전달하고, AI는 **patch가 아니라 전체 workflow JSON을 다시 반환**한다.

이유:

- patch merge가 복잡해지지 않는다.
- validation이 단순하다.
- UI는 항상 최신 완성본만 표시하면 된다.

### 3.5 적용 흐름

사용자가 `이 workflow 적용` 클릭 시 confirmation:

```text
이 workflow를 보드 `default`에 적용합니다.
- 생성 예정 task: 7개
- dependency link: 8개
- 즉시 실행 가능 ready task: 2개
- 대기 todo task: 5개

계속할까요?
```

적용 후:

```text
Workflow 적용 완료: wf_xxxxx
생성됨: 7개 / 기존 재사용: 0개
```

board reload 후 카드에 기존 workflow chip 표시.

---

## 4. Backend 설계

## 4.1 새 module: `kanban_webui/workflow_drafts.py`

역할:

- draft 저장/조회/수정/삭제
- attachment 저장/텍스트 추출
- proposal validation
- revision history 관리

저장 위치:

```text
{settings.state_dir}/workflow-drafts/{draft_id}/draft.json
{settings.state_dir}/workflow-drafts/{draft_id}/attachments/{attachment_id}-{safe_filename}
```

권한:

- directory: `0700`
- files: `0600` 권장

Draft shape:

```json
{
  "draft_id": "wfd_20260506_ab12cd34",
  "board": "default",
  "status": "draft",
  "created_at": 1770000000,
  "updated_at": 1770000300,
  "applied_at": null,
  "applied_instance_id": null,
  "planner_profile": "dev_plan",
  "original_prompt": "사용자 원문",
  "attachments": [
    {
      "attachment_id": "att_01",
      "filename": "requirements.md",
      "content_type": "text/markdown",
      "size_bytes": 12345,
      "stored_path": "/home/.../.hermes/kanban-webui/workflow-drafts/.../requirements.md",
      "text_excerpt": "...",
      "truncated": false
    }
  ],
  "revisions": [
    {
      "revision": 1,
      "user_prompt": "초기 요청",
      "proposal": { "...": "WorkflowProposal" },
      "validation": { "ok": true, "errors": [], "warnings": [] },
      "created_at": 1770000000
    }
  ],
  "current_revision": 1
}
```

---

## 4.2 새 module: `kanban_webui/workflow_planner.py`

역할:

- Hermes Agent CLI를 호출해 AI proposal 생성
- prompt assembly
- dynamic agent profile resolution
- JSON parsing/repair
- timeout/error handling

추천 command:

```bash
HOME=<real_user_home> \
HERMES_HOME=<real_user_home>/.hermes \
hermes -p <planner_profile> chat \
  -Q \
  --ignore-rules \
  --toolsets none \
  --max-turns 1 \
  --source kanban-webui-planner \
  -q '<assembled prompt>'
```

중요:

- `<planner_profile>`은 hard-code하지 않는다.
- 기본 profile 선택 순서:
  1. request의 `planner_profile`이 on-disk profile이면 사용
  2. `HERMES_KANBAN_WORKFLOW_PLANNER_PROFILE`이 on-disk profile이면 사용
  3. `dev_plan`이 존재하면 사용
  4. `default`가 존재하면 사용
  5. 첫 번째 on-disk profile 사용
  6. profile이 하나도 없으면 API 400/503으로 명확히 실패
- proposal task assignee 후보도 현재 board의 `known_assignees` 중 `on_disk=true` 목록을 prompt에 전달한다.
- `subprocess.run([...], shell=False)` 사용.
- shell string 조합 금지.
- `timeout` 적용.
- stdout만 JSON parse 대상.
- stderr의 `session_id: ...`는 필요하면 별도 metadata로 저장하되 UI에는 노출하지 않아도 됨.
- 실패 시 502/504로 명확히 반환.

설정 env:

```text
HERMES_KANBAN_WORKFLOW_AI_ENABLED=1             # 기본값 1. 0/false/no면 비활성화
HERMES_KANBAN_WORKFLOW_PLANNER_PROFILE=dev_plan # optional override. 존재하지 않으면 fallback
HERMES_KANBAN_WORKFLOW_PLANNER_TIMEOUT_SECONDS=180
HERMES_KANBAN_WORKFLOW_MAX_FILES=5
HERMES_KANBAN_WORKFLOW_MAX_FILE_BYTES=262144
HERMES_KANBAN_WORKFLOW_MAX_TOTAL_ATTACHMENT_CHARS=60000
HERMES_KANBAN_WORKFLOW_MAX_STEPS=20
```

`AI_ENABLED`는 기본 활성화한다. 배포 안정성을 위해 env로 끌 수만 있게 둔다.

## 4.3 Proposal JSON schema

AI가 반환해야 하는 strict JSON:

```json
{
  "schema_version": 1,
  "title": "string",
  "summary": "string",
  "strategy": "string",
  "applyable": true,
  "questions": ["string"],
  "warnings": ["string"],
  "steps": [
    {
      "key": "research",
      "title": "조사: ...",
      "body": "작업 상세 본문. worker가 바로 실행할 수 있어야 함.",
      "assignee": "dev_plan",
      "skills": ["writing-plans"],
      "priority": 5,
      "status": "ready",
      "depends_on": [],
      "acceptance_criteria": ["..."],
      "max_runtime_seconds": null
    }
  ]
}
```

제약:

- `steps`: 1~20개
- `key`: `^[a-z][a-z0-9_-]{1,31}$`
- `depends_on`: 같은 proposal 안의 key만 허용
- cycle 금지
- `assignee`: 현재 board의 `known_assignees` 중 `on_disk=true` profile만 사용 권장
- 모르는 profile을 만들지 말 것. 애매하면 `null` 또는 planner가 받은 fallback profile 사용
- `dev_plan`은 예시 기본값일 뿐, 모든 사용자 환경에 존재한다고 가정하지 말 것
- `status`: root step은 `ready`, dependency가 있으면 `todo` 권장
- `triage`는 사용자 확인이 필요한 step에만 사용
- task id는 생성하지 말 것. 실제 id는 apply 시 backend가 생성

---

## 4.4 AI prompt template

Backend가 AI에 전달할 prompt는 대략 이런 형태.

```text
You are designing a Hermes Kanban workflow.
Return ONLY valid JSON matching schema_version=1.
Do not create tasks. Do not call tools. Do not include markdown fences.

Available agent profiles are dynamic for this installation. Use ONLY this list:
{available_profiles_json}

Profile selection rules:
- Prefer a profile whose name/capability fits the step.
- If unsure, use the planner fallback profile: {fallback_profile}.
- Do not invent profile names.
- If no suitable profile exists, set assignee to null and add a warning.

Kanban execution rules:
- Root steps with no depends_on should be status=ready.
- Dependent steps should be status=todo.
- Dependencies become task_links on apply.
- A worker must receive enough context in each task body.
- Prefer small focused tasks and explicit acceptance criteria.
- Avoid cycles.
- Do not invent task IDs.

User prompt:
...

Attachments:
filename: requirements.md
excerpt:
...

Previous proposal, if revision:
...

Revision request, if revision:
...
```

MVP에서는 한국어 UI 사용자 기준으로 task title/body는 한국어를 기본으로 하되, 코드/명령/파일명은 원문 유지.

---

## 4.5 Validation 함수

`workflow_drafts.py` 또는 `workflows.py`에 공통 validator를 둔다.

필수 validation:

1. JSON object 여부
2. `schema_version == 1`
3. title/summary 존재
4. step 개수 제한
5. step key 형식/중복 검사
6. dependency target 존재 검사
7. DAG cycle 검사
8. status 허용값 검사
9. priority int 범위 검사
10. body/title 길이 제한
11. attachment path가 draft directory 밖으로 나가지 않는지 검사
12. assignee profile이 없으면 warning 또는 null 처리

Validation 결과:

```json
{
  "ok": true,
  "errors": [],
  "warnings": ["assignee 'foo'는 on-disk profile이 아니므로 미지정으로 바꿨습니다."]
}
```

AI 출력이 invalid면:

- 1회 자동 repair prompt 시도
- 그래도 실패하면 422/502로 UI에 표시

---

## 4.6 기존 `workflows.py` 전환/정리

현재 `instantiate_workflow()`는 built-in `template_id`를 기준으로 동작한다. 이번 요구사항에서는 template 기반 Workflow 생성은 유지하지 않으므로, public/user-facing template registry와 template endpoint를 보존하지 않는다.

변경 방향:

1. `workflow_template_id` DB 필드는 기존 task metadata compatibility 때문에 당장 제거하지 않는다.
   - prompt workflow에는 값 예시: `ai-draft-v1` 또는 `prompt-generated-v1`
   - UI label은 `템플릿`이 아니라 `Workflow source`/`생성 방식`으로 바꾼다.
2. built-in template registry는 삭제하거나 내부 테스트 fixture로만 축소한다.
3. 생성 로직은 template 객체가 아니라 `WorkflowProposal.steps`를 직접 받는 generic helper로 바꾼다.
4. 기존 template endpoints는 제거하거나 deprecated response를 반환한다.
   - 추천 MVP: frontend에서 호출 제거 + backend route 제거
   - API 호환성을 더 신경 쓰려면 410 Gone으로 명확히 반환

신규/변경 함수 예:

```python
def preview_workflow_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize an AI-generated workflow proposal for display."""
    ...


def instantiate_workflow_steps(
    conn,
    *,
    source_id: str,
    source_name: str,
    steps: list[dict[str, Any]],
    original_prompt: str,
    attachments: list[dict[str, Any]],
    instance_id: str | None,
    created_by: str,
    workspace_kind: str,
    workspace_path: str | None,
    tenant: str | None,
    priority_offset: int,
) -> dict[str, Any]:
    """Create Kanban tasks and task_links from validated workflow steps."""
    ...
```

Prompt workflow apply는 proposal을 바로 `instantiate_workflow_steps()`에 넘긴다.

Step normalization 예:

```python
{
    "source_id": "ai-draft-v1",
    "source_name": proposal["title"],
    "steps": [
        {
            "key": step["key"],
            "title": step["title"],
            "body": build_task_body(step, proposal, attachments),
            "assignee": step.get("assignee"),
            "skills": step.get("skills", []),
            "priority": step.get("priority", 0),
            "status": normalized_status(step),
            "depends_on": step.get("depends_on", []),
            "max_runtime_seconds": step.get("max_runtime_seconds"),
        }
    ],
}
```

Template-specific naming should not leak into new code except where existing DB field names require it.

## 4.7 Task body 생성 규칙

각 task body에는 worker가 독립적으로 읽어도 실행 가능하도록 context를 넣는다.

예:

```markdown
## 작업 목표
...

## 상세 지시
...

## Acceptance Criteria
- ...
- ...

## Workflow Context
- Draft ID: wfd_...
- Instance ID: wf_...
- Step: implement_backend
- Depends on: research

## 원본 사용자 요청
...

## 첨부 파일
- requirements.md
  - 저장 경로: /home/.../.hermes/kanban-webui/workflow-drafts/.../requirements.md
  - 요약/발췌: ...

## Worker Notes
- parent task 완료 결과를 먼저 확인하세요.
- 필요한 경우 `kanban_show`로 parent summary를 읽고 진행하세요.
```

주의:

- 첨부 전문을 모든 task에 반복 삽입하면 task body가 과도하게 커질 수 있다.
- MVP는 `첨부 요약/발췌 + 저장 경로`를 넣고, 첫 root task에는 더 긴 attachment context를 넣는 방식 추천.

---

## 4.8 API 설계

### `POST /api/workflows/drafts`

초기 설계 생성.

Request: `multipart/form-data`

```text
prompt: string
planner_profile: string optional
max_steps: int optional
files: UploadFile[] optional
```

Response:

```json
{
  "draft_id": "wfd_...",
  "revision": 1,
  "proposal": { "...": "WorkflowProposal" },
  "validation": { "ok": true, "errors": [], "warnings": [] },
  "attachments": [ ... ]
}
```

### `POST /api/workflows/drafts/{draft_id}/revise`

수정 요청.

Request: `multipart/form-data` 또는 JSON + optional files. 단순 구현을 위해 multipart로 통일 추천.

```text
prompt: string
files: UploadFile[] optional
```

Response:

```json
{
  "draft_id": "wfd_...",
  "revision": 2,
  "proposal": { "...": "WorkflowProposal" },
  "validation": { "ok": true, "errors": [], "warnings": [] }
}
```

### `GET /api/workflows/drafts/{draft_id}`

현재 draft 조회.

### `POST /api/workflows/drafts/{draft_id}/instantiate`

최종 적용.

Request JSON:

```json
{
  "instance_id": "optional-user-value",
  "workspace_kind": "scratch",
  "workspace_path": null,
  "tenant": null,
  "priority_offset": 0
}
```

Response는 기존 instantiate response와 맞춘다.

```json
{
  "instance_id": "wf_...",
  "created": 7,
  "existing": 0,
  "tasks": [
    {
      "step_key": "research",
      "task_id": "t_...",
      "title": "조사: ...",
      "status": "ready",
      "assignee": "dev_plan",
      "existing": false
    }
  ]
}
```

### `DELETE /api/workflows/drafts/{draft_id}`

선택 사항. MVP에서는 없어도 되지만 cleanup에 유용.

---

## 5. Frontend 설계

## 5.1 `static/api.js`

추가 methods:

```js
createWorkflowDraft: (board, formData) => request(`/api/workflows/drafts?${boardQuery(board)}`, { method: 'POST', body: formData }),
reviseWorkflowDraft: (board, draftId, formData) => request(`/api/workflows/drafts/${encodeURIComponent(draftId)}/revise?${boardQuery(board)}`, { method: 'POST', body: formData }),
getWorkflowDraft: (board, draftId) => request(`/api/workflows/drafts/${encodeURIComponent(draftId)}?${boardQuery(board)}`),
instantiateWorkflowDraft: (board, draftId, payload) => request(`/api/workflows/drafts/${encodeURIComponent(draftId)}/instantiate?${boardQuery(board)}`, { method: 'POST', body: payload }),
```

주의: `FormData` body에는 `Content-Type` header를 직접 넣지 않는다.

## 5.2 `static/forms.js`

추가 함수:

```js
setupPromptWorkflowDialog(load)
renderPromptWorkflowProposal(root, proposal, validation)
collectPromptWorkflowForm(form)
handleDraftCreate(...)
handleDraftRevise(...)
handleDraftInstantiate(...)
```

기존 `renderWorkflowPreview()`는 steps/deps 표시가 이미 있으므로 재사용/확장한다.

추가 UI state:

```js
state.workflowDraft = null;
state.workflowDraftRevision = null;
```

## 5.3 `static/index.html`

기존 workflow modal을 template/prompt 탭으로 확장하지 않는다. Template 선택 UI를 제거하고 prompt designer 단일 화면으로 교체한다.

```html
<section id="workflowDesigner" class="workflow-designer">
  <textarea name="prompt" ...></textarea>
  <input type="file" name="files" multiple />
  <select name="planner_profile">...</select>
  <button data-draft-create>설계 생성</button>

  <div id="promptWorkflowProposal"></div>

  <textarea name="revision_prompt"></textarea>
  <button data-draft-revise>수정안 생성</button>
  <button data-draft-apply>이 workflow 적용</button>
</section>
```

삭제/변경 대상:

- `workflowTemplateSelect`
- template preview button/state
- template instantiate submit path
- `Workflow 템플릿` label

## 5.4 `static/style.css`

추가 스타일:

- `.workflow-designer`
- `.prompt-workflow-form`
- `.workflow-proposal-summary`
- `.workflow-warning-list`
- `.workflow-question-list`
- `.workflow-attachment-list`
- `.workflow-step.acceptance-criteria`

다크모드 기준:

- 기존 CSS variable만 사용
- hard-coded black/white 금지
- warning/question은 기존 token 색 계열 재사용

## 5.5 `static/i18n.js`

한국어/영어 label 추가:

```js
promptWorkflow: '프롬프트로 설계'
workflowPrompt: '요청 프롬프트'
workflowFiles: '첨부파일'
generateWorkflowDraft: '설계 생성'
reviseWorkflowDraft: '수정안 생성'
applyWorkflowDraft: '이 workflow 적용'
workflowWarnings: '주의사항'
workflowQuestions: '확인 필요'
workflowAcceptanceCriteria: '검증 기준'
```

## 5.6 cache busting

현재 static version `20260506-01` 사용 중.

변경 시 전체 import query를 새 버전으로 올린다.

예:

```text
20260506-02
```

테스트도 함께 갱신.

---

## 6. 보안/안전 설계

1. AI agent는 tool access 없이 실행
   - `--toolsets none`
   - `--max-turns 1`
   - `--ignore-rules`
2. AI는 실제 task 생성 API를 호출하지 못한다.
   - backend가 JSON만 받아 draft로 저장
3. shell injection 방지
   - `subprocess.run([...], shell=False)`
4. 파일 업로드 제한
   - 파일 수 제한
   - 파일당 byte 제한
   - 총 텍스트 char 제한
   - filename sanitize
   - path traversal 금지
5. 첨부파일은 MVP에 포함하되, planner 본문 추출 가능 여부를 분리한다.
   - text-like/PDF text layer: 추출 후 prompt에 포함
   - image/unsupported binary: 저장+metadata+warning, 의미 해석은 후속
6. prompt/raw output을 server log에 남기지 않기
7. draft file 권한 제한
8. 적용 전 confirmation 필수
9. invalid/cyclic workflow는 적용 불가
10. unknown assignee는 자동 생성하지 않고 warning 처리
11. secrets redaction은 자동 완벽 보장 불가. UI에 “첨부 내용은 AI planner에 전달됩니다” 안내 필요

---

## 7. 테스트 계획

## 7.1 Backend unit/API tests

새 파일: `tests/test_workflow_drafts.py`

### RED tests 먼저 작성

1. `POST /api/workflows/drafts` creates draft from prompt
   - fake planner가 deterministic JSON 반환
   - response에 `draft_id`, `revision=1`, proposal 포함

2. attachment upload stores sanitized file
   - `../evil.md` 같은 filename이 escape하지 못함
   - text excerpt 저장

3. invalid attachment rejected
   - max file count 초과
   - max size 초과
   - unsupported binary

4. proposal validator rejects duplicate step key

5. proposal validator rejects unknown dependency

6. proposal validator rejects cycle

7. root/dependent status normalization/warning
   - depends_on 있는 step이 `ready`면 `todo`로 조정하거나 warning

8. revision increments revision
   - previous proposal이 planner prompt에 포함되었는지 fake planner로 확인
   - `current_revision=2`

9. instantiate draft creates tasks and links
   - root task `ready`
   - child task `todo`
   - `workflow_template_id == prompt-generated-v1` 또는 draft template id
   - `current_step_key` 설정
   - `idempotency_key == workflow:<instance_id>:<step_key>`

10. instantiate is idempotent
    - 같은 draft/instance apply 재호출 시 existing reuse

11. cannot instantiate invalid draft

12. cannot revise already applied draft, 또는 revise하면 새 draft로 fork
    - MVP 추천: applied draft는 revise 금지

13. planner timeout returns clear API error

14. planner non-JSON output triggers repair once then succeeds/fails

## 7.2 Frontend static tests

`tests/test_static_smoke.py` 확장:

- AI workflow designer button/form 존재
- template workflow select/tab이 제거되었는지 확인
- file input 존재
- revision textarea 존재
- `api.createWorkflowDraft`, `api.reviseWorkflowDraft`, `api.instantiateWorkflowDraft` 존재
- i18n key 존재
- static version bump 확인

## 7.3 Existing tests

항상 실행:

```bash
.venv/bin/python -m pytest -q
node --check static/app.js static/forms.js static/api.js static/board.js static/drawer.js
python -m py_compile kanban_webui/workflow_drafts.py kanban_webui/workflow_planner.py kanban_webui/workflows.py kanban_webui/kanban_api.py
```

## 7.4 Browser QA

1. WebUI 실행
2. AI Workflow 설계 dialog 열기
3. prompt만으로 설계 생성
4. 첨부파일 포함 설계 생성
5. 수정 프롬프트로 revision 생성
6. 적용 전 board에 task가 생기지 않았는지 확인
7. 적용 후 task/link 생성 확인
8. dependency line과 drawer workflow section 확인
9. dark mode에서 readable 확인
10. browser console error 없음 확인

---

## 8. 구현 순서

## Phase 1 — Backend model/validator only

파일:

- `kanban_webui/workflow_drafts.py`
- `tests/test_workflow_drafts.py`

작업:

1. `WorkflowProposal` validation helper 작성
2. cycle/duplicate/unknown dependency 검사
3. draft file store skeleton 작성
4. fake planner 기반 tests 작성

검증:

```bash
.venv/bin/python -m pytest tests/test_workflow_drafts.py -q
```

## Phase 2 — Generic instantiate refactor + template 제거

파일:

- `kanban_webui/workflows.py`
- `tests/test_workflows.py`
- `tests/test_workflow_drafts.py`

작업:

1. built-in template registry와 template-specific public helpers를 제거/축소
2. `instantiate_workflow_steps()` 추출
3. prompt proposal steps를 직접 instantiate
4. template endpoint/UI 호출이 남아 있지 않도록 tests 갱신

검증:

```bash
.venv/bin/python -m pytest tests/test_workflows.py tests/test_workflow_drafts.py -q
```

## Phase 3 — Planner integration

파일:

- `kanban_webui/workflow_planner.py`
- `kanban_webui/config.py`
- `pyproject.toml`
- `tests/test_workflow_drafts.py`

작업:

1. `python-multipart` dependency 추가
2. PDF text extraction을 MVP에 넣는 경우 `pypdf` dependency 추가
3. env config 추가
4. Hermes CLI planner client 구현
5. dynamic planner profile resolution 구현
6. prompt assembly
7. JSON parse/repair
8. timeout/error handling

검증:

- unit test는 fake subprocess로 실행
- 실제 Hermes CLI smoke는 수동/옵션으로만 수행

## Phase 4 — API routes

파일:

- `kanban_webui/kanban_api.py`
- `tests/test_workflow_drafts.py`

작업:

1. `POST /api/workflows/drafts`
2. `POST /api/workflows/drafts/{draft_id}/revise`
3. `GET /api/workflows/drafts/{draft_id}`
4. `POST /api/workflows/drafts/{draft_id}/instantiate`

검증:

```bash
.venv/bin/python -m pytest tests/test_workflow_drafts.py -q
```

## Phase 5 — Frontend UI

파일:

- `static/index.html`
- `static/forms.js`
- `static/api.js`
- `static/state.js`
- `static/style.css`
- `static/i18n.js`
- `tests/test_static_smoke.py`

작업:

1. template workflow UI 제거
2. AI workflow designer form/file input 추가
3. proposal render 추가
4. revision UI 추가
5. apply confirmation 추가
6. loading/error/toast 처리
7. static cache version bump

검증:

```bash
node --check static/app.js static/forms.js static/api.js static/board.js static/drawer.js
.venv/bin/python -m pytest tests/test_static_smoke.py -q
```

## Phase 6 — Docs and final QA

파일:

- `README.md`
- `docs/INSTALL.md` 또는 `docs/WORKFLOWS.md`
- `docs/TROUBLESHOOTING.md`

문서 내용:

- AI workflow designer 사용법
- 첨부파일 제한
- planner profile 설정
- `kanban-worker` disabled pitfall
- Hermes CLI auth/model/provider 문제 해결

최종 검증:

```bash
git diff --check
.venv/bin/python -m pytest -q
node --check static/app.js static/forms.js static/api.js static/board.js static/drawer.js
python -m py_compile kanban_webui/workflow_drafts.py kanban_webui/workflow_planner.py kanban_webui/workflows.py kanban_webui/kanban_api.py
```

Browser:

- prompt → draft → revise → apply end-to-end
- console error 없음
- dark/light mode 확인

---

## 9. 위험 요소와 대응

### 9.1 AI가 잘못된 DAG를 반환

대응:

- strict JSON schema
- backend validation
- repair 1회
- invalid면 적용 버튼 disabled

### 9.2 AI가 너무 큰 workflow를 생성

대응:

- max steps default 8, hard cap 20
- UI에서 step count 표시
- 너무 큰 경우 warning

### 9.3 첨부파일이 크거나 binary

대응:

- 첨부파일 업로드/저장은 MVP 필수
- size/file count cap
- text-like 파일은 본문 추출
- PDF는 text layer 추출을 MVP에 포함할지 `pypdf` 의존성으로 판단
- image/unsupported binary는 저장+warning으로 처리하고 OCR/의미 해석은 후속
- task body에는 full blob 복사 대신 저장 경로/파일명/요약/발췌만 포함

### 9.4 planner CLI 호출이 느림

대응:

- synchronous MVP + spinner + timeout
- 후속으로 background job/session polling 전환 가능

### 9.5 profile hallucination

대응:

- current known assignees/on_disk profiles를 prompt에 제공
- unknown assignee는 validation warning 후 null 또는 동적 fallback profile로 보정
- `dev_plan` 존재를 가정하지 않고 profile list를 매번 API/DB에서 조회

### 9.6 적용 중 일부 task만 생성되는 문제

대응:

- transaction 사용
- 기존 `instantiate_workflow()`처럼 하나의 DB connection/transaction에서 처리
- 실패 시 rollback

### 9.7 중복 적용

대응:

- `instance_id` 기반 idempotency
- 기본 instance id는 `wf_<draft_id short>_r<revision>`
- 재호출 시 existing task reuse

---

## 10. 확정된 결정 사항

사용자 피드백 반영 후 확정된 방향:

1. **기존 템플릿 기반 Workflow 생성은 유지하지 않음**
   - 수동 task 생성 기능은 유지
   - workflow 생성 경로는 AI prompt designer로 대체
   - template select/preview/apply UI는 제거
   - template API는 제거 또는 410 Gone 처리

2. **AI planner 기본 활성화**
   - 기본값: enabled
   - 운영자가 필요하면 `HERMES_KANBAN_WORKFLOW_AI_ENABLED=0`으로 비활성화 가능

3. **기본 planner profile은 `dev_plan` 추천, 그러나 동적 fallback 필수**
   - 사용자마다 agent profile 구성이 다르므로 `dev_plan` hard-code 금지
   - fallback 순서: request 선택값 → env override → `dev_plan` if exists → `default` if exists → 첫 on-disk profile
   - task assignee 후보도 현재 설치의 on-disk profile 목록에서만 선택하도록 prompt/validator 설계

4. **첨부파일은 MVP에 포함**
   - upload/store/reference는 필수
   - text-like 파일 본문 추출은 필수
   - PDF text layer 추출은 MVP 포함 후보로 계획
   - image/OCR/음성 의미 해석은 후속

5. **수정 방식은 prompt revision만 지원**
   - inline edit/drag dependency edit는 후속

6. **적용 후 자동 dispatch하지 않음**
   - 사용자가 board에서 확인 후 기존 dispatcher/manual dispatch 흐름 사용

7. **applied draft는 수정 금지**
   - 수정하려면 새 draft로 fork 또는 새로 생성

## 11. 예상 변경 파일 목록

Backend:

```text
kanban_webui/workflow_drafts.py      신규
kanban_webui/workflow_planner.py     신규
kanban_webui/workflows.py            template registry 제거 + generic step instantiate
kanban_webui/kanban_api.py           API routes 추가
kanban_webui/config.py               planner/upload env 추가
pyproject.toml                       python-multipart 추가, PDF 지원 시 pypdf 추가
```

Frontend:

```text
static/index.html
static/api.js
static/forms.js
static/state.js
static/style.css
static/i18n.js
```

Tests:

```text
tests/test_workflow_drafts.py        신규
tests/test_workflows.py              template removal/generic instantiate regression
tests/test_static_smoke.py           UI/static contract
```

Docs:

```text
README.md
docs/WORKFLOWS.md 또는 docs/INSTALL.md
docs/TROUBLESHOOTING.md
```

---

## 12. 추천 최종 구현 기준

작업 완료로 볼 기준:

1. 사용자가 prompt만 입력해 workflow draft를 받을 수 있다.
2. 사용자가 text file을 첨부하면 AI 설계에 반영된다.
3. draft가 생성되어도 실제 task는 생성되지 않는다.
4. 수정 프롬프트를 입력하면 revision이 생성되고 이전 proposal을 대체한다.
5. invalid workflow는 apply할 수 없다.
6. apply 버튼을 누르면 기존 Kanban task와 parent/child links가 생성된다.
7. 생성된 task는 drawer/card에서 workflow 정보가 보인다.
8. root task만 ready, dependent task는 todo로 생성된다.
9. full pytest, node syntax, browser smoke가 통과한다.
10. 설치/문서에 AI workflow designer 사용법과 제한사항이 적혀 있다.
