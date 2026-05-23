from __future__ import annotations

from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys

import pytest


def test_static_shell_contains_required_ui_contracts(client):
    index = client.get('/').text
    assert 'Hermes KanbanWebUI' in index
    assert 'langToggle' in index
    assert 'boardSelect' in index
    assert 'taskCreateBtn' in index
    assert '/static/app.js' in index

    root = Path(__file__).resolve().parents[1]
    for rel in ['static/app.js', 'static/board.js', 'static/drawer.js', 'static/monitor.js', 'static/i18n.js', 'static/update.js', 'static/design-tokens.css', 'DESIGN.md']:
        assert (root / rel).is_file(), rel


def test_app_update_static_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    api = (root / 'static' / 'api.js').read_text(encoding='utf-8')
    update = (root / 'static' / 'update.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    for phrase in [
        'id="updateDialog"',
        'id="updateCommitList"',
        'id="updateStatusMessage"',
        'data-update-current',
        'data-update-remote',
        'data-update-later',
        'data-update-apply',
    ]:
        assert phrase in index

    assert './update.js?v=20260522-zh-tw' in app
    assert 'setupAppUpdatePrompt' in app
    for phrase in ['appUpdateStatus', '/api/app/update-status', 'applyAppUpdate', '/api/app/update']:
        assert phrase in api
    for phrase in [
        'setupAppUpdatePrompt',
        'kanbanDismissedUpdateCommit',
        'api.appUpdateStatus',
        'api.applyAppUpdate',
        'pollHealthUntilReady',
        'location.reload()',
        'updateCommitList',
        'updateDialog',
        '300000',
    ]:
        assert phrase in update
    for key in ['updateAvailable', 'updateApply', 'updateLater', 'updateChecking', 'updateRestarting', 'updateBlocked', 'updateNoCommits']:
        assert key in i18n
    for css_class in ['.update-modal', '.update-commit-list', '.update-status']:
        assert css_class in style


def test_static_javascript_parses():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is required for static JavaScript syntax checks')
    root = Path(__file__).resolve().parents[1]
    checker = root / 'scripts' / 'check_static_js.py'
    assert checker.is_file()
    subprocess.run([sys.executable, str(checker)], check=True, cwd=root)


def test_static_javascript_check_fails_without_modules(tmp_path):
    root = Path(__file__).resolve().parents[1]
    checker = root / 'scripts' / 'check_static_js.py'
    spec = importlib.util.spec_from_file_location('check_static_js', checker)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    empty_repo = tmp_path / 'repo'
    (empty_repo / 'static').mkdir(parents=True)
    with pytest.raises(RuntimeError, match='no static JavaScript modules found'):
        module.check_static_javascript(empty_repo)


def test_default_language_is_traditional_chinese():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')

    assert '<html lang="zh-Hant">' in index
    assert "DEFAULT_LANGUAGE = 'zh-Hant'" in i18n
    assert "'zh-Hant'" in i18n
    assert "['zh-Hant', 'en', 'ko']" in i18n
    assert '清楚好讀的任務營運看板' in index
    assert '清楚好讀的任務營運看板' in i18n
    assert '업데이트' not in index
    assert '확인 중' not in index
    assert 'LANGUAGE_TOGGLE_LABELS' in i18n
    assert 'nextLang' in app
    assert "storedBoard === 'default'" in app
    assert 'fallbackBoard = data.current' in app
    assert "lang() === 'ko'" not in app
    assert 'labels.ko[key]' not in i18n


def test_docs_describe_traditional_chinese_as_default_language():
    root = Path(__file__).resolve().parents[1]
    readme = (root / 'README.md').read_text(encoding='utf-8')
    design = (root / 'DESIGN.md').read_text(encoding='utf-8')
    changelog = (root / 'CHANGELOG.md').read_text(encoding='utf-8')

    assert 'Traditional Chinese (`zh-Hant`) UI by default' in readme
    assert 'English' in readme
    assert 'Traditional Chinese (`zh-Hant`) labels by default' in design
    assert 'Korean UI by default' not in readme
    assert 'Korean labels by default' not in design
    assert 'Korean default UI' not in changelog


def test_dark_mode_static_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    theme = (root / 'static' / 'theme.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    tokens = (root / 'static' / 'design-tokens.css').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'id="themeToggle"' in index
    assert 'aria-pressed="false"' in index
    assert 'style.css?v=20260522-zh-tw' in index
    assert 'app.js?v=20260522-zh-tw' in index
    assert './theme.js?v=20260522-zh-tw' in app
    assert 'setupThemeToggle' in app
    assert 'updateThemeToggleLabel' in app
    assert 'kanbanTheme' in theme
    assert 'prefers-color-scheme: dark' in theme
    assert 'document.documentElement.dataset.theme' in theme
    assert 'localStorage.setItem(THEME_STORAGE_KEY' in theme
    assert 'themeDark' in i18n
    assert 'themeLight' in i18n
    assert ':root[data-theme="dark"]' in tokens
    assert 'color-scheme: dark' in tokens
    for token in ['--body-background', '--control-bg', '--card-bg', '--column-header-bg', '--edge-stroke']:
        assert token in tokens
        assert f'var({token})' in style


def test_dragdrop_pointer_contract_strings():
    root = Path(__file__).resolve().parents[1]
    dragdrop = (root / 'static' / 'dragdrop.js').read_text(encoding='utf-8')
    api = (root / 'static' / 'api.js').read_text(encoding='utf-8')
    for phrase in ['pointerdown', 'setPointerCapture', 'drag threshold', 'drop placeholder', 'autoScrollBoard', 'moveTask']:
        assert phrase in dragdrop
    for phrase in ['reorderTask', '/reorder']:
        assert phrase in api
    for phrase in ['reorderTask', 'before_id', 'after_id']:
        assert phrase in dragdrop
    for phrase in ['insertBefore', 'drop-placeholder']:
        assert phrase in dragdrop


def test_drawer_matches_dashboard_detail_controls():
    root = Path(__file__).resolve().parents[1]
    drawer = (root / 'static' / 'drawer.js').read_text(encoding='utf-8')
    api = (root / 'static' / 'api.js').read_text(encoding='utf-8')

    for phrase in [
        'data-action="triage"',
        'data-action="unblock"',
        'data-assignee-save',
        'data-priority-save',
        'bodyEditForm',
        'addParentSelect',
        'addChildSelect',
        'data-link-action',
        'data-home-platform',
        'workerLogContent',
    ]:
        assert phrase in drawer

    for phrase in ['homeChannels', 'subscribeHome', 'unsubscribeHome', 'linkTask', 'unlinkTask', 'taskLog']:
        assert phrase in api


def test_button_hover_keeps_ghost_text_readable():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert '.button.primary, .button:hover' not in style
    assert '.button.ghost { background: var(--ghost-bg); color: var(--ink); }' in style
    assert '.button.ghost:hover { background: var(--ghost-hover-bg); color: var(--ink); border-color: var(--border); }' in style
    assert '.button.ghost.danger-btn:hover' in style


def test_drawer_forms_do_not_overflow_grid_tracks():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, .8fr) minmax(96px, .4fr) auto' in style
    assert 'minmax(220px, 1fr)' not in style
    assert '.inline-form label, .dependency-form { display: grid; gap: 6px; color: var(--muted); font-weight: 700; min-width: 0; }' in style
    assert '.inline-form input, .inline-form select, .dependency-form select, .dependency-form button { width: 100%; min-width: 0; }' in style
    assert '.dependency-grid > div { min-width: 0; }' in style


def test_dependency_visual_options_and_focus_overlay_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    lines = (root / 'static' / 'dependency-lines.js').read_text(encoding='utf-8')
    drawer = (root / 'static' / 'drawer.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'id="dependencyView"' in index
    for mode in ['focus', 'all', 'blocked', 'off']:
        assert f'value="{mode}"' in index
    assert 'setupDependencyControls' in app
    assert 'renderDependencyOverlay' in board
    assert 'data-parent-count' in board
    assert 'data-child-count' in board
    for phrase in ['dependency-overlay', 'dependency-edge', 'dependency-focus', 'dependency-dim', 'dependency-blocked']:
        assert phrase in lines
        assert phrase in style
    assert 'dependency-mini-map' in drawer
    assert 'dependencyMiniMap' in drawer


def test_task_create_options_live_in_modal_not_toolbar():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    forms = (root / 'static' / 'forms.js').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    for phrase in [
        'id="taskCreateBtn"',
        'id="taskDialog"',
        'id="taskCreateForm"',
        'id="taskTitle"',
        'id="taskBody"',
        'id="taskAssignee"',
        'id="taskStatus"',
    ]:
        assert phrase in index

    for removed in ['id="quickCreateForm"', 'id="quickTitle"', 'id="quickAssignee"', 'id="quickStatus"']:
        assert removed not in index

    assert 'setupTaskCreateDialog' in forms
    assert "document.getElementById('taskCreateBtn')" in forms
    assert "document.dispatchEvent(new CustomEvent('kanban:open-task-create'" in board
    assert "kanban:open-task-create" in forms
    assert "document.getElementById('taskCreateBtn').click()" in app
    for key in ['taskCreate', 'taskCreateHint', 'taskTitlePlaceholder', 'taskBodyPlaceholder']:
        assert key in i18n
    for css_class in ['.toolbar-actions', '.task-field-grid', '.task-modal']:
        assert css_class in style



def test_unassigned_tasks_are_visually_flagged():
    root = Path(__file__).resolve().parents[1]
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')
    tokens = (root / 'static' / 'design-tokens.css').read_text(encoding='utf-8')

    for phrase in [
        'const isUnassigned = !task.assignee;',
        'profileMissing',
        'profileMissingShort',
        'missing-assignee-chip',
        'profile-missing-badge',
        "data-assignee-state=\"${isUnassigned ? 'missing' : 'assigned'}\"",
        "safeStatus}${isUnassigned ? ' is-unassigned' : ''}",
    ]:
        assert phrase in board
    for key in ['profileMissing', 'profileMissingShort']:
        assert key in i18n
    for css_class in ['.task-card.is-unassigned', '.profile-missing-badge', '.chips .missing-assignee-chip']:
        assert css_class in style
    assert './board.js?v=20260522-zh-tw' in app
    assert './i18n.js?v=20260522-zh-tw' in board
    for token in ['--warning-soft', '--warning-ring']:
        assert token in tokens


def test_operations_dashboard_static_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    api = (root / 'static' / 'api.js').read_text(encoding='utf-8')
    ops = (root / 'static' / 'operations.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    for phrase in ['id="opsToggleBtn"', 'id="opsPanel"']:
        assert phrase in index
    assert './operations.js?v=20260522-zh-tw' in app
    for phrase in ['opsSummary', '/api/ops/summary']:
        assert phrase in api
    for phrase in ['renderOperationsPanel', 'setupOperationsPanel', 'retry_queue', 'blocked_after_retries', 'retry_timing', 'openTaskDrawer']:
        assert phrase in ops
    for key in ['operations', 'opsOverview', 'opsRunning', 'opsRetryQueue', 'opsRetryQueueAdvisory', 'opsBlockedAfterRetries', 'opsEstimatedBackoffAdvisory', 'opsEstimatedBackoffAdvisoryColumn']:
        assert key in i18n
    for css_class in ['.ops-panel', '.ops-grid', '.ops-table', '.ops-chip']:
        assert css_class in style


def test_workflow_static_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    api = (root / 'static' / 'api.js').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    drawer = (root / 'static' / 'drawer.js').read_text(encoding='utf-8')
    forms = (root / 'static' / 'forms.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    for phrase in [
        'id="workflowBtn"',
        'id="workflowDialog"',
        'id="workflowForm"',
        'id="workflowPrompt"',
        'id="workflowPlannerProfile"',
        'id="workflowAttachments"',
        'id="workflowDraftPreview"',
        'id="workflowRevisionPrompt"',
        'data-workflow-plan',
        'data-workflow-revise',
        'data-workflow-apply',
    ]:
        assert phrase in index

    for removed in ['workflowTemplateSelect', 'Workflow 템플릿', 'workflowTemplates', 'workflowPreview', 'instantiateWorkflow']:
        assert removed not in index
        assert removed not in app

    for phrase in ['createWorkflowDraft', 'reviseWorkflowDraft', 'getWorkflowDraft', 'instantiateWorkflowDraft']:
        assert phrase in api

    for phrase in ['setupWorkflowDialog', 'workflowPrompt', 'api.createWorkflowDraft', 'api.reviseWorkflowDraft', 'api.instantiateWorkflowDraft', 'proposal?.applyable === false', 'workflowNotApplyable']:
        assert phrase in forms

    assert 'loadWorkflowTemplates' not in app
    assert 'populateWorkflowTemplateSelect' not in app
    assert 'workflow-chip' in board
    assert 'workflowDetailSection' in drawer
    for key in ['workflowCreate', 'workflowDesignerHint', 'workflowPrompt', 'workflowPlannerProfile', 'workflowAttachments', 'workflowRevise', 'workflowApply', 'workflowDraftStatus', 'workflowNotApplyable', 'workflowSteps']:
        assert key in i18n
    for css_class in ['.workflow-step-list', '.workflow-step', '.workflow-chip', '.workflow-meta', '.workflow-draft-actions', '.workflow-attachment-list']:
        assert css_class in style


def test_board_columns_fill_available_resolution_width():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    tokens = (root / 'static' / 'design-tokens.css').read_text(encoding='utf-8')

    assert '--column-min-width:' in tokens
    assert '--kanban-column-count' in board
    assert "root.style.setProperty('--kanban-column-count'" in board
    assert '.board { position: relative; display: grid;' in style
    assert 'grid-template-columns: repeat(var(--kanban-column-count, 6), minmax(var(--column-min-width), 1fr));' in style
    assert 'width: var(--column-width)' not in style
    assert 'min-width: var(--column-width)' not in style
    assert '.board-column { position: relative; min-width: 0;' in style


def test_mobile_rwd_board_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'id="columnNav"' in index
    for phrase in ['columnNav', 'column-nav-button', 'data-column-target', 'scrollIntoView', 'aria-current']:
        assert phrase in board
    for phrase in [
        '.column-nav',
        '.column-nav-button',
        '@media (max-width: 760px)',
        '@media (max-width: 430px)',
        '.column-nav { position: sticky;',
        'scroll-snap-type: x mandatory',
        'grid-template-columns: repeat(var(--kanban-column-count, 6), minmax(calc(100vw - 32px), 1fr))',
    ]:
        assert phrase in style


def test_kpi_row_uses_dynamic_status_count_when_archived_is_visible():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    render_kpis = board.split('export function renderKpis(data) {', 1)[1].split('export function renderBoard(data) {', 1)[0]

    assert '--kpi-column-count' in render_kpis
    assert "root.style.setProperty('--kpi-column-count'" in render_kpis
    assert 'grid-template-columns: repeat(var(--kpi-column-count, 6), minmax(120px, 1fr));' in style
    assert 'overflow-x: auto;' in style
    assert '.kpi-row { grid-template-columns: repeat(3, 1fr); }' not in style
    assert '.kpi-row { grid-template-columns: repeat(2, 1fr); }' not in style


def test_dependency_lines_render_above_column_backgrounds_below_cards():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert '.board-column { position: relative; min-width: 0;' in style
    assert '.board-column { position: relative; z-index: 1;' not in style
    assert '.cards { position: relative; z-index: 2;' in style
    assert '.task-card { position: relative;' in style
    assert '.dependency-overlay { position: absolute; left: 0; top: 0; z-index: 1;' in style


def test_dependency_edges_fan_out_shared_endpoints():
    root = Path(__file__).resolve().parents[1]
    lines = (root / 'static' / 'dependency-lines.js').read_text(encoding='utf-8')

    for phrase in [
        'assignEdgePorts',
        'sourceOffset',
        'targetOffset',
        'portOffset',
        'data-source-offset',
        'data-target-offset',
    ]:
        assert phrase in lines


def test_blueprint_dependency_ports_create_links_from_board():
    root = Path(__file__).resolve().parents[1]
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    lines = (root / 'static' / 'dependency-lines.js').read_text(encoding='utf-8')
    dragdrop = (root / 'static' / 'dragdrop.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')

    for phrase in [
        'class="dependency-port child-port"',
        'class="dependency-port parent-port"',
        'data-link-role="child"',
        'data-link-role="parent"',
        'data-link-task-id',
    ]:
        assert phrase in board

    for phrase in [
        "import { api }",
        'setupBlueprintLinking',
        'pointerdown',
        'pointermove',
        'pointerup',
        'document.elementFromPoint',
        'relationFromPorts',
        'api.linkTask(state.board',
        'dependency-preview-edge',
        "cardPoint(board, parentCard, 'left'",
        "cardPoint(board, childCard, 'right'",
        'const direction = to.x >= from.x ? 1 : -1;',
        'from.x + direction * dx',
    ]:
        assert phrase in lines

    assert "ev.target.closest('.dependency-port')" in dragdrop
    assert '.dependency-port.child-port { right:' in style
    assert '.dependency-port.parent-port { left:' in style
    assert '.board.is-linking' in style
    assert '.dependency-preview-edge' in style
    for key in ['parentPortHint', 'childPortHint', 'linkCreatedToast', 'linkInvalidToast']:
        assert key in i18n


def test_board_polish_improves_card_scanability_and_accessibility():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'aria-label="切換語言"' in index
    for phrase in [
        'const safeStatus = safeStatusClass(task.status);',
        'const statusLabel = escapeHtml(t(task.status));',
        'const cardAriaLabel',
        'aria-label="${cardAriaLabel}"',
        'class="task-status-pill ${safeStatus}"',
        'class="task-drag-hint"',
        'task-card-title',
        'task-card-preview',
        'empty-column-card',
        'addTaskToColumn',
        'if (ev.target !== el) return;',
    ]:
        assert phrase in board
    for key in ['openTaskHint', 'dragTaskHint', 'taskStatusLabel', 'emptyColumnHint', 'addTaskToColumn', 'languageToggle']:
        assert key in i18n
    for phrase in [
        '.task-card:focus-visible',
        '.button:focus-visible, select:focus-visible, input:focus-visible, textarea:focus-visible, .mini-add:focus-visible, .column-nav-button:focus-visible',
        '.task-status-pill',
        '.task-drag-hint',
        '.empty-column-card',
        '-webkit-line-clamp: 3;',
    ]:
        assert phrase in style


def test_issue6_progressive_disclosure_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    for phrase in ['id="moreActionsBtn"', 'id="moreActionsPanel"', 'aria-controls="moreActionsPanel"', 'data-secondary-action']:
        assert phrase in index
    toolbar = index.split('<div class="toolbar-actions">', 1)[1].split('<div class="more-actions-panel"', 1)[0]
    assert 'id="taskCreateBtn"' in toolbar
    for advanced_id in ['newBoardBtn', 'opsToggleBtn', 'workflowBtn', 'bulkBtn']:
        assert f'id="{advanced_id}"' not in toolbar
    for phrase in ['setupMoreActionsMenu', 'moreActionsBtn', "ev.key === 'Escape'", 'aria-expanded', 'moreActionsPanel.hidden']:
        assert phrase in app
    for key in ['moreActions', 'advancedActions', 'closeActions']:
        assert key in i18n
    for phrase in ['.more-actions', '.more-actions-panel', '[data-secondary-action]', '@media (max-width: 760px)']:
        assert phrase in style


def test_issue6_compact_summary_and_card_signal_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'id="kpiRow" class="compact-summary"' in index
    for phrase in ['class="summary-chip"', 'aria-label="${escapeHtml(`${t(status)}: ${count}`)}"', '--summary-chip-count']:
        assert phrase in board
    assert 'class="kpi"' not in board
    for phrase in ['card-primary-meta', 'card-secondary-meta', 'card-hermes-signal', 'hermesSignals', 'reviewSignal', 'prSignal', 'blockReason']:
        assert phrase in board
    for key in ['blockedSignal', 'liveSignal', 'dependenciesSignal', 'commentsSignal', 'reviewSignal', 'prSignal']:
        assert key in i18n
    for phrase in ['.compact-summary', '.summary-chip', '.card-primary-meta', '.card-secondary-meta', '.card-hermes-signal', '-webkit-line-clamp: 2;', '.task-drag-hint { margin-left: auto;']:
        assert phrase in style


def test_issue6_drawer_progressive_hermes_sections_contract():
    root = Path(__file__).resolve().parents[1]
    drawer = (root / 'static' / 'drawer.js').read_text(encoding='utf-8')
    i18n = (root / 'static' / 'i18n.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    for phrase in [
        'drawer-section overview-section',
        'drawer-section blocker-lifecycle-section',
        'drawer-section dependencies-section',
        'drawer-section worker-runs-section',
        'drawer-section comments-events-section',
        'drawer-section worker-log-section',
        'reviewMetadataSection',
        'github.com/',
        '<details class="drawer-section',
    ]:
        assert phrase in drawer
    for key in ['overview', 'blockerLifecycle', 'workerRunsMonitor', 'commentsEvents', 'reviewMetadata', 'claimHeartbeat']:
        assert key in i18n
    for phrase in ['.drawer-section[open]', '.drawer-section summary', '.review-metadata-list', '.lifecycle-actions']:
        assert phrase in style


def test_issue6_deeplink_and_mobile_overflow_contract():
    root = Path(__file__).resolve().parents[1]
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    state = (root / 'static' / 'state.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    for phrase in ['new URLSearchParams(location.search).get(\'board\')', 'queryBoard', 'activeQueryBoard', 'history.replaceState', 'setBoard(activeQueryBoard)']:
        assert phrase in app
    assert 'queryBoard' in state
    for phrase in ['html, body { min-height: 100%; overflow-x: clip; }', 'max-width: 100%;', 'minmax(calc(100vw - 32px), 1fr)', 'minmax(calc(100vw - 16px), 1fr)']:
        assert phrase in style
