export const LANGUAGE_ORDER = ['zh-Hant', 'en', 'ko'];
export const LANGUAGE_TOGGLE_LABELS = { 'zh-Hant': '繁中', en: 'EN', ko: 'KO' };
export const DEFAULT_LANGUAGE = 'zh-Hant';

export const labels = {
  'zh-Hant': {
    subtitle: '清楚好讀的任務營運看板', newBoard: '新增看板', refresh: '重新整理', themeDark: '切換深色', themeLight: '切換淺色', languageToggle: '切換語言', quickTitle: '輸入任務標題後按 Enter',
    taskCreate: '新增任務', taskCreateHint: '需要設定標題、說明、代理 profile 與狀態時，在這裡建立新 task。', taskTitlePlaceholder: '任務標題', taskBodyPlaceholder: '任務說明／指示（選填）',
    openTaskHint: '開啟任務詳情', dragTaskHint: '拖曳移動', taskStatusLabel: '任務狀態', emptyColumnHint: '可用右上角＋在此狀態新增任務', addTaskToColumn: '新增任務到欄位',
    assignee: '負責 profile', create: '新增', created: '建立時間', createdToast: '已建立', search: '搜尋標題／內容／ID', allAssignees: '全部負責人', unassigned: '未指定', profileMissing: '尚未指定負責 profile', profileMissingShort: '需要 profile', agentProfile: 'profile', manualAssignee: '手動', showArchived: '顯示封存',
    bulkCreate: '批次新增', boardName: '看板名稱', description: '說明', cancel: '取消', bulkHint: '每行輸入一個任務。', loading: '載入中…',
    workflow: 'Workflow', workflowCreate: '建立 AI Workflow', workflowDesignerHint: '用提示詞與附件設計任務 DAG，核准後套用成真正的 Kanban task。', workflowPrompt: 'Workflow 提示詞', workflowPromptPlaceholder: '描述目標、交付物、限制與期望步驟數', workflowPlannerProfile: 'Planner profile', workflowAttachments: '附件', workflowPlan: '規劃', workflowPlanning: 'AI 正在設計 workflow 草稿…', workflowRevise: '修改', workflowRevisionPlaceholder: '描述要調整的步驟／profile／依賴關係', workflowApply: '套用', workflowDraftStatus: '草稿狀態', workflowDraftEmpty: '輸入提示詞並按「規劃」後會顯示草稿。', workflowNotApplyable: '這份草稿目前還不能套用。請先解決問題後送出修改。', workflowInstance: 'Instance ID', workflowStep: '目前步驟', workflowSteps: '步驟',
    updateAvailable: '有新版本可用', updateTitle: 'KanbanWebUI 更新', updateApply: '更新並重新啟動', updateLater: '稍後', updateChecking: '正在檢查更新狀態…', updateRestarting: '正在套用更新…伺服器重新啟動後頁面會自動重載。', updateBlocked: '無法自動更新', updateNoCommits: '沒有 commit 明細', updateStatusStale: '更新狀態暫時無法重新確認，以下顯示上次快取結果',
    triage: '分流', todo: '待辦', ready: '就緒', running: '執行中', blocked: '卡住', done: '完成', archived: '封存',
    title: '標題', body: '內容', noDescription: '沒有說明', priority: '優先級', status: '狀態', workspace: '工作區', createdBy: '建立者',
    comments: '留言', events: '事件', runs: '執行紀錄', monitor: 'Live Run Monitor', context: '脈絡', log: '紀錄', workerLog: 'Worker 紀錄',
    dependencies: '依賴關係', parents: '上游', children: '下游', parent: '上游', child: '下游', chooseTask: '選擇任務', none: '無', remove: '移除',
    parentPortHint: '左側上游連接點：拖曳到另一個 task 的右側下游連接點，建立上游關係', childPortHint: '右側下游連接點：拖曳到另一個 task 的左側上游連接點，建立下游關係', linkCreatedToast: '已建立上游／下游連結', linkInvalidToast: '只能連接左側上游連接點與右側下游連接點。', linkSameTaskToast: '同一個 task 不能連到自己。',
    dependencyViewFocus: '關係線：以選取為中心', dependencyViewAll: '關係線：全部', dependencyViewBlocked: '關係線：卡住', dependencyViewOff: '關係線：隱藏',
    dependencyMap: '關係地圖', currentTask: '目前任務', noDependencies: '沒有上游／下游連結',
    notifyHomeChannels: '通知 home channel', noHomeChannels: '沒有設定 home channel', noWorkerLog: '尚無 worker 紀錄',
    complete: '完成', block: '標記卡住', unblock: '解除卡住', cancelRunning: '取消執行／回收', archive: '封存', save: '儲存', close: '關閉', addComment: '新增留言',
    moreActions: '更多', advancedActions: '進階功能', closeActions: '關閉進階功能', overview: '概覽', blockerLifecycle: '卡住與生命週期', workerRunsMonitor: 'Worker 執行與監控', commentsEvents: '留言與事件', reviewMetadata: 'PR／Review 資訊', claimHeartbeat: 'Claim／Heartbeat', blockedSignal: '卡住', liveSignal: '執行中', dependenciesSignal: '依賴', commentsSignal: '留言', reviewSignal: 'Review', prSignal: 'PR', operations: 'Operations', opsOverview: 'Operations 總覽', opsRunning: '執行中', opsHeartbeatOverdue: 'Heartbeat 逾時', opsRetryQueue: 'Retry queue', opsRetryQueueAdvisory: 'Retry queue（advisory）', opsBlockedAfterRetries: '重試後卡住', opsRecentFailures: '近期失敗', opsNoRunning: '沒有執行中的任務', opsNoRetry: '沒有可重試項目', opsNoBlockedAfterRetries: '沒有重試後卡住的任務', opsNoFailures: '近期沒有失敗事件', opsEligibleNow: '現在可執行', opsEstimatedEligibleNow: '預估現在可執行', opsEstimatedWait: '預估等待', opsAttempt: '嘗試次數', opsLastError: '最後錯誤', opsOpenTask: '開啟任務', opsEstimatedBackoffAdvisory: '顯示的 backoff／eligible_at 是依目前失敗資訊估算的參考值，dispatcher 尚未強制套用。', opsEstimatedBackoffAdvisoryColumn: '預估 backoff（參考）', empty: '無'
  },
  ko: {
    subtitle: '읽기 쉬운 작업 운영 보드', newBoard: '보드 추가', refresh: '새로고침', themeDark: '다크로 전환', themeLight: '라이트로 전환', languageToggle: '언어 전환', quickTitle: '작업 제목을 입력하고 Enter',
    taskCreate: 'Task 추가', taskCreateHint: '필요할 때만 제목, 설명, 담당 프로필, 상태를 입력해 새 task를 생성합니다.', taskTitlePlaceholder: '작업 제목', taskBodyPlaceholder: '작업 설명/지시사항(선택)',
    openTaskHint: '작업 상세 열기', dragTaskHint: '드래그 이동', taskStatusLabel: '작업 상태', emptyColumnHint: '오른쪽 위 +로 이 상태에 작업을 추가하세요', addTaskToColumn: '컬럼에 작업 추가',
    assignee: '담당 프로필', create: '추가', created: '생성일', createdToast: '생성됨', search: '작업 제목/내용/ID 검색', allAssignees: '전체 담당자', unassigned: '미지정', profileMissing: '담당 프로필 미지정', profileMissingShort: '프로필 필요', agentProfile: '프로필', manualAssignee: '수동', showArchived: '보관함 표시',
    bulkCreate: '일괄 추가', boardName: '보드 이름', description: '설명', cancel: '취소', bulkHint: '한 줄에 작업 하나씩 입력하세요.', loading: '불러오는 중…',
    workflow: 'Workflow', workflowCreate: 'AI Workflow 생성', workflowDesignerHint: '프롬프트와 첨부파일로 작업 DAG를 설계한 뒤 승인 시 실제 Kanban task로 적용합니다.', workflowPrompt: 'Workflow 프롬프트', workflowPromptPlaceholder: '목표, 산출물, 제약, 원하는 단계 수를 설명하세요', workflowPlannerProfile: 'Planner 프로필', workflowAttachments: '첨부파일', workflowPlan: '설계', workflowPlanning: 'AI가 workflow 초안을 설계하는 중…', workflowRevise: '수정', workflowRevisionPlaceholder: '변경할 단계/담당 프로필/의존성을 설명하세요', workflowApply: '적용', workflowDraftStatus: 'Draft 상태', workflowDraftEmpty: '프롬프트를 입력하고 설계를 누르면 초안이 표시됩니다.', workflowNotApplyable: '아직 적용할 수 없는 초안입니다. 질문을 해결한 뒤 수정 요청을 보내세요.', workflowInstance: 'Instance ID', workflowStep: '현재 단계', workflowSteps: '단계',
    updateAvailable: '새 업데이트 사용 가능', updateTitle: 'KanbanWebUI 업데이트', updateApply: '업데이트 후 재시작', updateLater: '나중에', updateChecking: '업데이트 상태 확인 중…', updateRestarting: '업데이트 적용 중… 서버가 재시작되면 자동으로 새로고침합니다.', updateBlocked: '자동 업데이트 불가', updateNoCommits: '커밋 목록 없음', updateStatusStale: '업데이트 상태를 다시 확인하지 못해 마지막 캐시 결과를 표시합니다',
    triage: '분류', todo: '대기', ready: '준비', running: '실행중', blocked: '막힘', done: '완료', archived: '보관',
    title: '제목', body: '본문', noDescription: '설명 없음', priority: '우선순위', status: '상태', workspace: '워크스페이스', createdBy: '생성자',
    comments: '댓글', events: '이벤트', runs: '런', monitor: 'Live Run Monitor', context: '컨텍스트', log: '로그', workerLog: 'Worker 로그',
    dependencies: '의존성', parents: '부모', children: '자식', parent: '부모', child: '자식', chooseTask: '작업 선택', none: '없음', remove: '삭제',
    parentPortHint: '왼쪽 부모 포트: 다른 task의 오른쪽 자식 포트로 드래그해 부모로 연결', childPortHint: '오른쪽 자식 포트: 다른 task의 왼쪽 부모 포트로 드래그해 자식으로 연결', linkCreatedToast: '부모/자식 연결됨', linkInvalidToast: '왼쪽 부모 포트와 오른쪽 자식 포트만 연결할 수 있습니다.', linkSameTaskToast: '같은 task끼리는 연결할 수 없습니다.',
    dependencyViewFocus: '관계선: 선택 중심', dependencyViewAll: '관계선: 전체', dependencyViewBlocked: '관계선: 막힘', dependencyViewOff: '관계선: 숨김',
    dependencyMap: '관계 지도', currentTask: '현재 작업', noDependencies: '연결된 부모/자식 없음',
    notifyHomeChannels: '홈 채널 알림', noHomeChannels: '설정된 홈 채널 없음', noWorkerLog: 'worker 로그 없음',
    complete: '완료', block: '막기', unblock: '해제', cancelRunning: '실행 취소/회수', archive: '보관', save: '저장', close: '닫기', addComment: '댓글 추가',
    moreActions: '더보기', advancedActions: '고급 기능', closeActions: '고급 기능 닫기', overview: '개요', blockerLifecycle: '막힘/수명주기', workerRunsMonitor: 'Worker 실행/모니터', commentsEvents: '댓글/이벤트', reviewMetadata: 'PR/Review 정보', claimHeartbeat: 'Claim/Heartbeat', blockedSignal: '막힘', liveSignal: '실행중', dependenciesSignal: '의존성', commentsSignal: '댓글', reviewSignal: 'Review', prSignal: 'PR', operations: 'Operations', opsOverview: 'Operations 개요', opsRunning: '실행 중', opsHeartbeatOverdue: 'Heartbeat 지연', opsRetryQueue: 'Retry queue', opsRetryQueueAdvisory: 'Retry queue (advisory)', opsBlockedAfterRetries: '재시도 후 막힘', opsRecentFailures: '최근 실패', opsNoRunning: '실행 중인 작업 없음', opsNoRetry: '재시도 후보 없음', opsNoBlockedAfterRetries: '재시도 후 막힌 작업 없음', opsNoFailures: '최근 실패 이벤트 없음', opsEligibleNow: '지금 가능', opsEstimatedEligibleNow: '예상으로 지금 가능', opsEstimatedWait: '예상 대기', opsAttempt: '시도', opsLastError: '마지막 오류', opsOpenTask: '열기', opsEstimatedBackoffAdvisory: '표시된 backoff/eligible_at은 현재 실패 정보로 계산한 참고용 추정치이며 dispatcher가 아직 강제하지 않습니다.', opsEstimatedBackoffAdvisoryColumn: '예상 backoff (참고)', empty: '없음'
  },
  en: {
    subtitle: 'Readable operations board', newBoard: 'New board', refresh: 'Refresh', themeDark: 'Switch dark', themeLight: 'Switch light', languageToggle: 'Switch language', quickTitle: 'Type a task title and press Enter',
    taskCreate: 'Create task', taskCreateHint: 'Open this dialog only when you need to set title, details, agent profile, and status for a new task.', taskTitlePlaceholder: 'Task title', taskBodyPlaceholder: 'Task details/instructions (optional)',
    openTaskHint: 'Open task details', dragTaskHint: 'Drag to move', taskStatusLabel: 'Task status', emptyColumnHint: 'Use the top-right + to add a task in this status', addTaskToColumn: 'Add task to column',
    assignee: 'Agent profile', create: 'Create', created: 'Created', createdToast: 'Created', search: 'Search title/body/ID', allAssignees: 'All assignees', unassigned: 'Unassigned', profileMissing: 'Agent profile missing', profileMissingShort: 'Needs profile', agentProfile: 'profile', manualAssignee: 'manual', showArchived: 'Show archived',
    bulkCreate: 'Bulk create', boardName: 'Board name', description: 'Description', cancel: 'Cancel', bulkHint: 'One task per line.', loading: 'Loading…',
    workflow: 'Workflow', workflowCreate: 'Create AI workflow', workflowDesignerHint: 'Design a task DAG from a prompt and attachments, then approve it into real Kanban tasks.', workflowPrompt: 'Workflow prompt', workflowPromptPlaceholder: 'Describe goals, outputs, constraints, and desired step count', workflowPlannerProfile: 'Planner profile', workflowAttachments: 'Attachments', workflowPlan: 'Plan', workflowPlanning: 'AI is designing a workflow draft…', workflowRevise: 'Revise', workflowRevisionPlaceholder: 'Describe step/profile/dependency changes', workflowApply: 'Apply', workflowDraftStatus: 'Draft status', workflowDraftEmpty: 'Enter a prompt and click Plan to preview a draft.', workflowNotApplyable: 'This draft is not applyable yet. Resolve questions and send a revision.', workflowInstance: 'Instance ID', workflowStep: 'Current step', workflowSteps: 'steps',
    updateAvailable: 'Update available', updateTitle: 'KanbanWebUI update', updateApply: 'Update and restart', updateLater: 'Later', updateChecking: 'Checking update status…', updateRestarting: 'Applying update… this page will reload after the server restarts.', updateBlocked: 'Automatic update blocked', updateNoCommits: 'No commit details', updateStatusStale: 'Could not refresh update status; showing the last cached result',
    triage: 'Triage', todo: 'Todo', ready: 'Ready', running: 'Running', blocked: 'Blocked', done: 'Done', archived: 'Archived',
    title: 'Title', body: 'Body', noDescription: 'No description', priority: 'Priority', status: 'Status', workspace: 'Workspace', createdBy: 'Created by',
    comments: 'Comments', events: 'Events', runs: 'Runs', monitor: 'Live Run Monitor', context: 'Context', log: 'Log', workerLog: 'Worker log',
    dependencies: 'Dependencies', parents: 'Parents', children: 'Children', parent: 'Parent', child: 'Child', chooseTask: 'Choose task', none: 'None', remove: 'Remove',
    parentPortHint: 'Left parent port: drag to another task right child port to link as parent', childPortHint: 'Right child port: drag to another task left parent port to link as child', linkCreatedToast: 'Parent/child linked', linkInvalidToast: 'Connect one left parent port with one right child port.', linkSameTaskToast: 'A task cannot link to itself.',
    dependencyViewFocus: 'Lines: Focus', dependencyViewAll: 'Lines: All', dependencyViewBlocked: 'Lines: Blocked', dependencyViewOff: 'Lines: Hidden',
    dependencyMap: 'Dependency map', currentTask: 'Current task', noDependencies: 'No parent/child links',
    notifyHomeChannels: 'Notify home channels', noHomeChannels: 'No home channels configured', noWorkerLog: 'No worker log yet',
    complete: 'Complete', block: 'Block', unblock: 'Unblock', cancelRunning: 'Cancel / reclaim', archive: 'Archive', save: 'Save', close: 'Close', addComment: 'Add comment',
    moreActions: 'More', advancedActions: 'Advanced actions', closeActions: 'Close advanced actions', overview: 'Overview', blockerLifecycle: 'Blockers & lifecycle', workerRunsMonitor: 'Worker runs & monitor', commentsEvents: 'Comments & events', reviewMetadata: 'PR / review metadata', claimHeartbeat: 'Claim / heartbeat', blockedSignal: 'Blocked', liveSignal: 'Live', dependenciesSignal: 'Dependencies', commentsSignal: 'Comments', reviewSignal: 'Review', prSignal: 'PR', operations: 'Operations', opsOverview: 'Operations overview', opsRunning: 'Running now', opsHeartbeatOverdue: 'Heartbeat overdue', opsRetryQueue: 'Retry queue', opsRetryQueueAdvisory: 'Retry queue (advisory)', opsBlockedAfterRetries: 'Blocked after retries', opsRecentFailures: 'Recent failures', opsNoRunning: 'No running tasks', opsNoRetry: 'No retry candidates', opsNoBlockedAfterRetries: 'No tasks blocked after retries', opsNoFailures: 'No recent failure events', opsEligibleNow: 'Eligible now', opsEstimatedEligibleNow: 'Estimated eligible now', opsEstimatedWait: 'Estimated wait', opsAttempt: 'Attempt', opsLastError: 'Last error', opsOpenTask: 'Open task', opsEstimatedBackoffAdvisory: 'Estimated backoff and eligible_at are advisory until dispatcher-level backoff is implemented.', opsEstimatedBackoffAdvisoryColumn: 'Estimated backoff (advisory)', empty: 'None'
  }
};

function normalizeLang(value) {
  return LANGUAGE_ORDER.includes(value) ? value : DEFAULT_LANGUAGE;
}

let currentLang = normalizeLang(localStorage.getItem('kanbanLang'));

export function lang() { return currentLang; }
export function nextLang(current = currentLang) {
  const index = LANGUAGE_ORDER.indexOf(normalizeLang(current));
  return LANGUAGE_ORDER[(index + 1) % LANGUAGE_ORDER.length];
}
export function setLang(next) { currentLang = normalizeLang(next); localStorage.setItem('kanbanLang', currentLang); applyI18n(); }
export function t(key) { return (labels[currentLang] && labels[currentLang][key]) || labels[DEFAULT_LANGUAGE][key] || key; }

export function applyI18n(root = document) {
  root.documentElement?.setAttribute('lang', currentLang);
  root.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  root.querySelectorAll('[data-i18n-aria-label]').forEach(el => { el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel)); });
  const toggle = root.getElementById?.('langToggle');
  if (toggle) toggle.textContent = LANGUAGE_TOGGLE_LABELS[nextLang()];
}
