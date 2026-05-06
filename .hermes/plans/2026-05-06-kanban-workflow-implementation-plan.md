---
title: KanbanWebUI workflow 기능 상세 구현 계획
status: planned
created: 2026-05-06
workspace: <repo-root>
scope: planning-only
---

# KanbanWebUI workflow 기능 상세 구현 계획

## 0. 요약

`workflow` 기능은 **여러 Kanban task를 정해진 단계와 의존관계로 한 번에 생성하고, 각 task가 어떤 workflow template/step에 속하는지 WebUI에서 보고 관리하는 기능**으로 구현한다.

MVP에서는 별도 실행 엔진을 만들지 않고, 기존 Hermes Kanban의 안정적인 실행 모델을 그대로 사용한다.

- 실행 순서: 기존 `task_links` 부모/자식 의존성과 `todo -> ready` promotion 재사용
- 실행 주체: 기존 `assignee` = Hermes profile 재사용
- 실행 기록: 기존 `task_runs.step_key` 재사용
- workflow 식별: 기존 `tasks.workflow_template_id`, `tasks.current_step_key`, `tasks.idempotency_key` 재사용
- UI: template 선택/미리보기/생성 + drawer의 workflow 섹션 + card chip

즉, MVP 정의는 **BPM/상태머신 엔진이 아니라 “template 기반 task bundle 생성 + 진행 시각화”**다.

---

## 1. 조사 결과

### 1.1 기존 계획 파일 발견 여부

저장소 내부와 workspace 전체에서 다음을 찾았으나 기존 `.hermes/plans` 또는 workflow 계획 문서는 발견되지 않았다.

- `<repo-root>/.hermes`: 없음
- repo 내 `*plan*` 파일: 없음
- workspace 내 `*workflow*` 파일: 없음
- 세션 검색: `HermesKanban`, `workflow_template_id`, `current_step_key`, `v2 workflow` 결과 없음

따라서 이 문서는 현재 코드와 Hermes Kanban DB의 forward-compatible 필드를 기준으로 작성한다.

### 1.2 Hermes Kanban DB에 이미 있는 workflow 기반

Hermes core 쪽 `hermes_cli/kanban_db.py`에는 workflow v2를 위한 필드가 이미 있다.

- `tasks.workflow_template_id TEXT`
- `tasks.current_step_key TEXT`
- `task_runs.step_key TEXT`

중요 주석:

- `workflow_template_id/current_step_key`는 “v2 workflow routing” forward-compat 필드
- 현재 v1 dispatcher는 이 필드를 routing에 사용하지 않음
- `claim_task()` 시점에 `tasks.current_step_key`가 `task_runs.step_key`로 복사됨

의미:

- DB schema 변경 없이 WebUI가 workflow step 정보를 기록할 수 있다.
- worker 실행 이력에도 step key가 남는다.
- 단, 자동 routing/advance 엔진은 아직 없다.

### 1.3 현재 KanbanWebUI API 상태

`kanban_webui/kanban_api.py` 기준:

- `UpdateTaskBody`에는 이미 `workflow_template_id`, `current_step_key`가 있음
- `WRITEABLE_TASK_FIELDS`에도 두 필드가 포함됨
- `PATCH /api/tasks/{task_id}`로 두 필드 갱신 가능
- `CreateTaskBody`에는 아직 workflow 필드가 없음
- `POST /api/tasks` / `POST /api/tasks/bulk-create`는 `kanban_db.create_task()`만 호출하므로 생성 시 workflow 필드를 직접 넣지 못함
- 생성 후 direct SQL/PATCH 방식으로 workflow 필드를 채울 수 있음

### 1.4 현재 serializer/UI 상태

`serializers.task_dict()`는 `dataclasses.asdict(task)`를 그대로 반환하므로 `workflow_template_id`, `current_step_key`, `idempotency_key`, `skills`가 이미 API 응답에 포함될 수 있다.

현재 UI:

- `static/board.js`: card chip은 assignee/tenant/priority/progress만 표시
- `static/drawer.js`: meta/action/body/dependencies/notify/comments/runs/events/log 표시
- workflow 전용 card chip, drawer section, template 생성 dialog는 없음
- dependency visualization은 이미 존재하므로 workflow step 간 연결을 그대로 활용 가능

### 1.5 테스트 구조

현재 WebUI 테스트 패턴:

- API/수명주기: `tests/test_task_lifecycle.py`
- board endpoints: `tests/test_board_endpoints.py`
- static contract: `tests/test_static_smoke.py`
- JS syntax: `node --check static/*.js`

workflow도 같은 방식으로 먼저 contract/API/static 테스트를 추가한다.

---

## 2. 목표와 비목표

## 2.1 MVP 목표

1. **Workflow template 목록 제공**
   - WebUI에서 사용할 built-in template을 API로 조회한다.
   - template schema validation을 제공한다.
   - JSON 기반 user template 확장 여지를 둔다.

2. **Workflow instantiate**
   - template을 선택해 여러 task를 한 번에 생성한다.
   - step 간 의존관계를 `task_links`로 연결한다.
   - 각 task에 `workflow_template_id`, `current_step_key`를 기록한다.
   - 각 step의 기본 `assignee`, `skills`, `priority`, `body`, `status`를 적용한다.

3. **Dry-run preview**
   - 실제 생성 전 생성될 step/task 제목, profile, 의존관계, 초기 status를 미리 보여준다.
   - invalid template/override는 생성 전에 거부한다.

4. **Board/card workflow 표시**
   - workflow task card에 template/step chip을 표시한다.
   - 검색/필터와 충돌하지 않게 작게 표시한다.

5. **Drawer workflow section**
   - 현재 task의 workflow template/step을 표시한다.
   - 같은 workflow로 생성된 sibling step들을 보여준다.
   - 각 step의 status와 parent/child 관계를 빠르게 이동할 수 있게 한다.

6. **기존 dispatcher와 호환**
   - workflow 때문에 dispatcher를 수정하지 않는다.
   - 실행 순서는 기존 parent dependency가 보장한다.
   - profile assignment가 있어야 자동 dispatch된다.

## 2.2 MVP 비목표

아래는 이번 MVP에서 제외한다.

- 시각적 workflow graph editor
- 조건부 분기/loop/parallel join expression engine
- dispatcher가 `workflow_template_id/current_step_key`로 자동 profile routing하는 기능
- WebUI에서 template 자체를 편집/저장하는 기능
- 별도 workflow status machine 도입
- cron/webhook 기반 workflow trigger
- Hermes core schema 변경

---

## 3. 핵심 설계 결정

## 3.1 Workflow는 “step task들의 DAG”로 표현한다

각 workflow step은 기존 Kanban task 하나다.

```text
workflow template
  ├─ step: plan       -> task A
  ├─ step: implement  -> task B, parent=A
  ├─ step: review     -> task C, parent=B
  └─ step: fix        -> task D, parent=C
```

장점:

- 기존 Kanban board/dispatcher/worker/log/notification 기능을 그대로 사용
- 부모/자식 dependency overlay와 자연스럽게 통합
- 완료된 parent의 summary/metadata가 child worker context에 자동 포함됨

## 3.2 `current_step_key`는 “이 task가 담당하는 step”을 뜻한다

이름은 `current_step_key`지만 MVP에서는 workflow instance의 전역 current pointer가 아니라 **task row의 step key**로 사용한다.

예시:

- plan task: `current_step_key = "plan"`
- implement task: `current_step_key = "implement"`
- review task: `current_step_key = "review"`

이 값은 claim 시 `task_runs.step_key`로 복사되어 attempt history에 남는다.

## 3.3 Workflow instance id는 `idempotency_key` prefix로 표현한다

현재 DB에는 `workflow_instance_id` 컬럼이 없다. Hermes core schema를 바꾸지 않기 위해 MVP에서는 workflow로 생성된 task의 `idempotency_key`를 다음 형태로 둔다.

```text
workflow:<instance_id>:<step_key>
```

예시:

```text
workflow:wf_20260506_152027_ab12cd:plan
workflow:wf_20260506_152027_ab12cd:implement
workflow:wf_20260506_152027_ab12cd:review
```

장점:

- 같은 요청 재시도 시 duplicate 생성을 피할 수 있음
- 같은 workflow instance의 step task를 조회할 수 있음
- 추가 schema 없이 MVP 가능

주의:

- 사용자가 직접 `idempotency_key`를 쓰는 task와 충돌하지 않도록 `workflow:` prefix를 예약한다.
- 장기적으로는 Hermes core에 `workflow_instance_id` 컬럼/테이블을 추가하는 방향이 더 명확하다.

## 3.4 Template format은 JSON 우선

현재 환경에서 PyYAML 의존을 전제로 하지 않는다. MVP template은 JSON으로 시작한다.

- built-in templates: `kanban_webui/workflow_templates.json` 또는 `kanban_webui/workflows.py` 내 상수
- user templates: 후속 단계에서 `$HERMES_KANBAN_HOME/workflow_templates/*.json`

MVP에서는 built-in JSON만 구현해도 충분하다. user template loading은 구조만 열어둔다.

---

## 4. Template schema 초안

```json
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
      "body": "요청:\n{body}\n\n상세 구현 계획을 작성하세요.",
      "assignee": "dev_plan",
      "skills": ["writing-plans"],
      "priority": 5,
      "status": "ready",
      "depends_on": []
    },
    {
      "key": "implement",
      "title": "구현: {title}",
      "body": "상위 기획 task의 결과를 바탕으로 구현하세요.",
      "assignee": "dev",
      "skills": ["test-driven-development"],
      "priority": 4,
      "status": "todo",
      "depends_on": ["plan"]
    },
    {
      "key": "review",
      "title": "리뷰: {title}",
      "body": "상위 구현 task의 변경을 리뷰하고 필요한 수정사항을 정리하세요.",
      "assignee": "dev_plan",
      "skills": ["requesting-code-review"],
      "priority": 3,
      "status": "todo",
      "depends_on": ["implement"]
    }
  ]
}
```

### 4.1 Step field 의미

| field | 의미 | MVP 필수 |
|---|---|---:|
| `key` | template 내부 unique step id | O |
| `title` | task title template | O |
| `body` | task body template | 선택 |
| `assignee` | 기본 Hermes profile | 선택 |
| `skills` | task별 force-load skill list | 선택 |
| `priority` | task priority | 선택 |
| `status` | 초기 status. `ready/todo/triage`만 허용 | 선택 |
| `depends_on` | parent step key 목록 | 선택 |
| `tenant` | 필요 시 tenant | 선택 |
| `max_runtime_seconds` | step별 실행 제한 | 선택 |

### 4.2 Validation 규칙

- template `id`는 `[a-z0-9][a-z0-9._-]*` 형식 권장
- step `key`는 template 내 unique
- `entry_step`은 존재해야 함
- 모든 `depends_on`은 존재하는 step key여야 함
- dependency graph는 cycle이 없어야 함
- step `status`는 `ready`, `todo`, `triage`만 허용
- skill 이름에는 comma 금지
- `title` 렌더링 결과는 공백 불가
- `workflow:`로 시작하는 idempotency key prefix는 workflow engine 전용

---

## 5. Backend 구현 계획

## 5.1 새 모듈: `kanban_webui/workflows.py`

역할:

- template dataclass/model 정의
- built-in template 로드
- template validation
- dry-run plan 생성
- commit instantiate 실행
- workflow instance 조회 helper

권장 구조:

```text
kanban_webui/workflows.py
kanban_webui/workflow_templates.json
```

핵심 함수:

```python
def list_templates() -> list[WorkflowTemplate]: ...
def get_template(template_id: str) -> WorkflowTemplate: ...
def validate_template(template: WorkflowTemplate) -> list[str]: ...
def preview_workflow(template_id: str, request: InstantiateRequest) -> WorkflowPreview: ...
def instantiate_workflow(conn, template_id: str, request: InstantiateRequest) -> WorkflowInstanceResult: ...
def workflow_instance_id() -> str: ...
def workflow_tasks_for_instance(conn, instance_id: str) -> list[Task]: ...
```

## 5.2 API endpoint 추가

`kanban_webui/kanban_api.py`에 추가한다.

### `GET /api/workflows/templates`

응답:

```json
{
  "templates": [
    {
      "id": "dev-plan-implement-review-v1",
      "name": "Plan → Implement → Review",
      "description": "...",
      "step_count": 3,
      "steps": [...]
    }
  ],
  "errors": []
}
```

### `GET /api/workflows/templates/{template_id}`

단일 template 상세.

### `POST /api/workflows/preview`

요청:

```json
{
  "template_id": "dev-plan-implement-review-v1",
  "title": "Kanban workflow UI 구현",
  "body": "요청 상세...",
  "assignee_overrides": { "review": "dev_plan" },
  "priority_offset": 0
}
```

응답:

```json
{
  "template_id": "dev-plan-implement-review-v1",
  "instance_id": "wf_preview",
  "steps": [
    {
      "step_key": "plan",
      "title": "기획: Kanban workflow UI 구현",
      "assignee": "dev_plan",
      "skills": ["writing-plans"],
      "status": "ready",
      "depends_on": []
    }
  ],
  "links": []
}
```

### `POST /api/workflows/instantiate`

실제 task 생성.

요청은 preview와 동일하되 `instance_id` optional 허용.

응답:

```json
{
  "ok": true,
  "board": "default",
  "template_id": "dev-plan-implement-review-v1",
  "instance_id": "wf_20260506_152027_ab12cd",
  "created": 3,
  "tasks": [
    { "step_key": "plan", "task_id": "t_...", "title": "...", "status": "ready" }
  ],
  "links": [
    { "parent_step": "plan", "child_step": "implement", "parent_id": "t_...", "child_id": "t_..." }
  ]
}
```

### `GET /api/workflows/instances/{instance_id}`

MVP에서 있으면 drawer sibling 조회가 쉬워진다.

조회 방식:

```sql
SELECT * FROM tasks
WHERE idempotency_key LIKE 'workflow:<instance_id>:%'
ORDER BY priority DESC, created_at ASC
```

응답:

```json
{
  "instance_id": "wf_...",
  "template_id": "dev-plan-implement-review-v1",
  "tasks": [...],
  "links": [...],
  "progress": { "done": 1, "total": 3 }
}
```

## 5.3 `CreateTaskBody` 확장 여부

선택지:

1. `CreateTaskBody`에 `workflow_template_id`, `current_step_key` 추가
2. workflow instantiate 내부에서 생성 후 direct update

추천: **1번**.

이유:

- API surface가 일관됨
- `POST /api/tasks`로 단일 workflow step task를 만들 수 있음
- `bulk-create`도 workflow field를 자연스럽게 받음

단, Hermes core `kanban_db.create_task()`는 아직 이 인자를 받지 않으므로 WebUI route는 생성 직후 기존 PATCH/direct update와 동일한 방식으로 두 필드를 업데이트해야 한다.

구현 패턴:

```python
# create_task 후
workflow_updates = {}
if payload.workflow_template_id is not None:
    workflow_updates["workflow_template_id"] = payload.workflow_template_id
if payload.current_step_key is not None:
    workflow_updates["current_step_key"] = payload.current_step_key
if workflow_updates:
    with kanban_db.write_txn(conn):
        conn.execute("UPDATE tasks SET ... WHERE id = ?", ...)
        _insert_event(conn, task_id, "workflow_attached", workflow_updates)
```

## 5.4 Instantiate 생성 알고리즘

1. template 로드/validate
2. request title/body/overrides normalize
3. step graph topological sort
4. dry-run plan 생성
5. commit이면 각 step 순서대로 `kanban_db.create_task()` 호출
   - `idempotency_key = f"workflow:{instance_id}:{step_key}"`
   - `parents = [created_task_id[parent_step] for parent_step in depends_on]`
   - status는 template status를 따르되, parents가 있으면 기본적으로 `todo`
6. 생성 직후 task row에 workflow fields update
   - `workflow_template_id = template.id`
   - `current_step_key = step.key`
7. link는 `create_task(parents=...)`가 기본 생성
8. 결과 반환

### 원자성 전략

`kanban_db.create_task()`가 내부 transaction을 열기 때문에 전체 workflow를 하나의 transaction으로 감싸기는 어렵다. MVP에서는 다음 방식으로 partial creation 위험을 낮춘다.

- 모든 validation을 생성 전에 수행
- DAG cycle 검증
- parent step 존재 검증
- status/skill/title 검증
- idempotency key 사용으로 retry-safe 보장
- 실패 시 응답에 이미 생성된 task 목록을 명확히 포함

후속 개선:

- Hermes core에 `create_tasks_batch()` 또는 workflow-native transaction helper 추가
- 또는 WebUI side에서 core create 로직을 복제하지 않고 core에 upstream PR

---

## 6. Frontend 구현 계획

## 6.1 API client

`static/api.js` 추가 메서드:

```js
workflows: () => request('/api/workflows/templates'),
workflowTemplate: id => request(`/api/workflows/templates/${encodeURIComponent(id)}`),
previewWorkflow: (board, payload) => request(`/api/workflows/preview?${new URLSearchParams({ board })}`, { method: 'POST', body: payload }),
instantiateWorkflow: (board, payload) => request(`/api/workflows/instantiate?${new URLSearchParams({ board })}`, { method: 'POST', body: payload }),
workflowInstance: (board, instanceId) => request(`/api/workflows/instances/${encodeURIComponent(instanceId)}?${new URLSearchParams({ board })}`)
```

## 6.2 새 모듈: `static/workflows.js`

역할:

- workflow dialog open/close
- template select rendering
- preview rendering
- instantiate submit
- drawer workflow section rendering helper
- workflow idempotency key parser

권장 함수:

```js
export function setupWorkflowControls(load) { ... }
export function workflowChip(task) { ... }
export function workflowInstanceId(task) { ... }
export async function renderWorkflowSection(task, boardData) { ... }
```

## 6.3 Top toolbar UI

`static/index.html` toolbar에 버튼 추가:

```html
<button id="workflowBtn" class="button ghost">⚙️ Workflow</button>
```

새 dialog:

```html
<dialog id="workflowDialog">
  <form id="workflowForm">
    <select id="workflowTemplate" name="template_id"></select>
    <input name="title" placeholder="Workflow 제목" />
    <textarea name="body" placeholder="요청 상세"></textarea>
    <section id="workflowPreview"></section>
    <button type="button" id="workflowPreviewBtn">미리보기</button>
    <button class="button primary">생성</button>
  </form>
</dialog>
```

UX 원칙:

- 생성 전 preview를 먼저 보여준다.
- preview 없이 submit하면 내부적으로 preview 후 생성하되, 오류를 명확히 표시한다.
- template step별 assignee override는 MVP에서 접은 상태(`<details>`)로 제공한다.

## 6.4 Board card 표시

`static/board.js` card chip에 workflow chip 추가:

```text
workflow_id / step_key
```

예시:

```text
workflow · implement
```

표시 조건:

- `task.workflow_template_id` 또는 `task.current_step_key`가 있을 때만
- 너무 길면 `step_key` 우선 표시, title에는 full template id

## 6.5 Drawer workflow section

`static/drawer.js`에서 meta/action과 body 사이 또는 dependencies 위에 추가한다.

내용:

- Template: `workflow_template_id || —`
- Step: `current_step_key || —`
- Instance: `workflow:<instance_id>`에서 파싱된 값
- Progress: `done/total`
- Steps list:
  - step key
  - task title/id
  - status dot
  - assignee/profile
  - click하면 해당 task drawer로 이동

UI 예시:

```text
Workflow
Template  : Plan → Implement → Review
Instance  : wf_20260506_152027_ab12cd
Progress  : 1 / 3

[done] plan       t_a1 · 기획: ...
[ready] implement t_b2 · 구현: ...
[todo] review     t_c3 · 리뷰: ...
```

## 6.6 Dark mode/style

새 class는 기존 token을 사용한다.

- `var(--panel-bg)`
- `var(--hairline)`
- `var(--muted)`
- `var(--accent)`
- `var(--card-bg)`
- `var(--ghost-bg)`

새 CSS 후보:

```css
.workflow-chip {}
.workflow-preview {}
.workflow-step-list {}
.workflow-step-node {}
.workflow-step-node.done|ready|todo|blocked|running {}
```

---

## 7. i18n 계획

`static/i18n.js`에 ko/en key 추가.

필수 key:

- `workflow`
- `workflows`
- `workflowTemplate`
- `workflowStep`
- `workflowInstance`
- `workflowPreview`
- `createWorkflow`
- `previewWorkflow`
- `workflowCreated`
- `workflowProgress`
- `noWorkflow`
- `assigneeOverrides`
- `stepDependsOn`

한국어 용어:

- `workflow`는 UI에서 “Workflow” 또는 “워크플로” 병기 가능
- `assignee`는 기존 선호에 맞춰 “담당 프로필” 사용
- `step`은 “단계” 사용

---

## 8. 테스트 계획

## 8.1 Backend contract tests

새 파일 후보: `tests/test_workflows.py`

### Template registry

- built-in templates load 가능
- template id unique
- step key unique
- depends_on unknown step 거부
- cycle 거부
- invalid initial status 거부
- comma-containing skill 거부

### API list/preview

- `GET /api/workflows/templates` returns templates
- `POST /api/workflows/preview` does not create tasks
- preview response includes steps/links/status/assignee/skills

### Instantiate

- `POST /api/workflows/instantiate` creates expected number of tasks
- each task has `workflow_template_id`
- each task has `current_step_key`
- each task has `idempotency_key` with `workflow:<instance_id>:<step_key>`
- dependency links match template `depends_on`
- first independent step is `ready`, dependent steps are `todo`
- duplicate instantiate with same `instance_id` does not duplicate tasks
- created task can be claimed and `task_runs.step_key` is populated

### Existing PATCH compatibility

- `PATCH /api/tasks/{id}` can set/clear workflow fields
- invalid title/status still does not partially mutate workflow fields

## 8.2 Static contract tests

`tests/test_static_smoke.py`에 추가:

- index has `workflowBtn`, `workflowDialog`, `workflowForm`
- app imports/setup calls `setupWorkflowControls`
- api.js has `workflows`, `previewWorkflow`, `instantiateWorkflow`, `workflowInstance`
- board.js renders workflow chip string/class
- drawer.js includes workflow section anchor/class
- i18n has workflow keys
- style has workflow classes using CSS variables

## 8.3 Browser QA

수동/브라우저 검증:

1. WebUI 열기
2. Workflow 버튼 클릭
3. template 선택
4. title/body 입력
5. preview 확인
6. 생성
7. board에 step task들이 표시되는지 확인
8. dependency overlay에서 순서가 보이는지 확인
9. drawer에서 workflow section과 step 이동 확인
10. dark mode에서 contrast 확인
11. console error 없음 확인

## 8.4 검증 명령

```bash
node --check static/app.js static/board.js static/dependency-lines.js static/drawer.js static/api.js static/i18n.js static/forms.js static/monitor.js static/dragdrop.js static/mobile.js static/state.js static/theme.js static/markdown.js static/workflows.js
.venv/bin/python -m pytest -q
git diff --check
```

---

## 9. 구현 단계별 작업 목록

## Phase 1 — Test/contract 먼저 추가

1. `tests/test_workflows.py` 생성
2. template registry validation 테스트 작성
3. preview/instantiate API 테스트 작성
4. `tests/test_static_smoke.py` workflow UI contract 추가

완료 기준:

- 새 테스트가 RED 상태로 실패한다.
- 실패 원인이 아직 구현되지 않은 workflow endpoint/UI 문자열임이 명확하다.

## Phase 2 — Backend template registry

1. `kanban_webui/workflows.py` 생성
2. built-in template 1개 추가: `dev-plan-implement-review-v1`
3. template validation 구현
4. preview plan 생성 구현
5. API route skeleton 추가

완료 기준:

- template list/preview tests GREEN
- 기존 tests regression 없음

## Phase 3 — Instantiate engine

1. `InstantiateWorkflowBody` pydantic model 추가
2. `POST /api/workflows/instantiate` 구현
3. `CreateTaskBody`에 workflow fields optional 추가
4. create/bulk create 후 workflow fields update helper 추가
5. idempotency key 기반 duplicate 방지 구현
6. `GET /api/workflows/instances/{instance_id}` 구현

완료 기준:

- instantiate tests GREEN
- created workflow step task의 DB/API fields 정상
- claim 후 run `step_key` 정상

## Phase 4 — Frontend workflow dialog

1. `static/workflows.js` 생성
2. `static/api.js` workflow methods 추가
3. `static/index.html` button/dialog 추가
4. `static/app.js`에서 `setupWorkflowControls(load)` 호출
5. preview/submit/toast/refresh 구현
6. cache query version bump

완료 기준:

- static contract GREEN
- `node --check` GREEN
- browser에서 preview/create 동작

## Phase 5 — Board/drawer 표시

1. `board.js` card chip 추가
2. `drawer.js` workflow section 추가
3. `style.css` workflow classes 추가
4. `i18n.js` ko/en keys 추가
5. dark mode contrast 확인

완료 기준:

- workflow task가 card에서 식별 가능
- drawer에서 같은 workflow의 step list 이동 가능
- dark/light 모두 읽기 가능

## Phase 6 — Docs/README

1. README API 목록에 workflow endpoints 추가
2. README 사용법에 workflow 생성 절차 추가
3. troubleshooting에 “생성됐는데 실행 안 됨 = 담당 프로필/ready 확인” 추가 또는 기존 안내 링크

완료 기준:

- 신규 사용자가 workflow 생성 → dispatch 조건을 이해할 수 있음

---

## 10. 리스크와 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| Hermes core dispatcher가 workflow fields를 무시함 | 자동 step routing 불가 | MVP는 `assignee`와 dependency로 실행 순서 제어 |
| 전체 workflow 생성이 완전 atomic하지 않음 | 중간 실패 시 일부 task 생성 가능 | prevalidate + idempotency key + 명확한 partial result 반환 |
| `idempotency_key`를 instance id 용도로 재사용 | 장기 모델 애매함 | `workflow:` prefix 예약, 후속 schema에서 `workflow_instance_id` 도입 |
| profile이 없는 assignee template | dispatch skip | UI preview에서 board assignees/profile 목록과 비교해 warning 표시 |
| workflow UI가 drawer를 복잡하게 함 | 가독성 저하 | collapsed section/details, card chip은 짧게 표시 |
| 다크모드 contrast 회귀 | 사용성 저하 | token 기반 CSS + browser QA |
| 기존 task create/bulk behavior 회귀 | 핵심 기능 손상 | 기존 lifecycle tests 유지 + workflow fields optional only |

---

## 11. 후속 v2 아이디어

MVP 이후에 고려할 기능:

1. Hermes core에 workflow-native helper 추가
   - `create_workflow_instance()`
   - `workflow_instances` table
   - atomic batch create

2. Dispatcher workflow routing
   - step key별 default profile/skill routing
   - unassigned step도 template route로 자동 assigned

3. Conditional branching
   - parent result metadata 기반 next step 선택

4. WebUI template editor
   - JSON editor + validation
   - preview graph

5. Workflow graph view
   - board dependency overlay와 별도로 instance timeline/graph 제공

6. Workflow clone/rerun
   - completed instance를 같은 inputs로 재생성

---

## 12. Definition of Done

MVP 완료 조건:

- [ ] `GET /api/workflows/templates`로 built-in workflow template 조회 가능
- [ ] `POST /api/workflows/preview`가 DB 변경 없이 step plan 반환
- [ ] `POST /api/workflows/instantiate`가 template 기반 task bundle 생성
- [ ] 생성된 모든 task에 `workflow_template_id/current_step_key/idempotency_key` 기록
- [ ] step dependency가 `task_links`로 생성되어 기존 promotion/dispatcher 흐름과 연결
- [ ] card에 workflow chip 표시
- [ ] drawer에 workflow section과 sibling step navigation 표시
- [ ] dark/light mode 모두 가독성 유지
- [ ] `node --check` 통과
- [ ] `.venv/bin/python -m pytest -q` 통과
- [ ] `git diff --check` 통과

---

## 13. 첫 구현 PR 추천 범위

첫 PR은 너무 크게 만들지 않기 위해 다음 범위로 제한한다.

1. Backend template registry
2. list/preview/instantiate/instance API
3. built-in template 1개
4. minimal workflow dialog
5. card chip + drawer section
6. tests/docs

제외:

- user template file loading
- template editor
- graph editor
- dispatcher routing 변경
- Hermes core schema 변경
