import { t } from './i18n.js?v=20260522-zh-tw';
import { escapeHtml } from './markdown.js?v=20260522-zh-tw';
import { openTaskDrawer } from './drawer.js?v=20260522-zh-tw';
import { attachDragHandlers } from './dragdrop.js?v=20260522-zh-tw';
import { clearDependencyFocus, focusDependencyTask, renderDependencyOverlay, selectDependencyTask } from './dependency-lines.js?v=20260522-zh-tw';

function safeStatusClass(status) {
  return ['triage', 'todo', 'ready', 'running', 'blocked', 'done', 'archived'].includes(status) ? status : 'unknown';
}

function taskMetadata(task) {
  return task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
}

function hasReviewSignal(task, meta) {
  const text = `${task.body_preview || ''} ${task.body || ''}`;
  return Boolean(meta.review_status || meta.findings || /review-required|approved|changes requested/i.test(text));
}

function hasPrSignal(task, meta) {
  const text = `${task.body_preview || ''} ${task.body || ''}`;
  return Boolean(meta.pr_url || meta.pr_number || /github\.com\/[^\s]+\/pull\/\d+/i.test(text));
}

function hermesSignals(task, parents, children) {
  const meta = taskMetadata(task);
  const blockReason = task.block_reason || meta.block_reason || '';
  const reviewSignal = hasReviewSignal(task, meta);
  const prSignal = hasPrSignal(task, meta);
  const signals = [];
  if (blockReason || task.status === 'blocked') signals.push(`<span class="card-hermes-signal blocked" title="${escapeHtml(blockReason || t('blockedSignal'))}">⛔ ${escapeHtml(t('blockedSignal'))}</span>`);
  if (task.status === 'running' || task.current_run_id) signals.push(`<span class="card-hermes-signal live">● ${escapeHtml(t('liveSignal'))}</span>`);
  if (parents || children) signals.push(`<span class="card-hermes-signal deps">↕ ${parents + children} ${escapeHtml(t('dependenciesSignal'))}</span>`);
  if (task.comment_count) signals.push(`<span class="card-hermes-signal comments">💬 ${Number(task.comment_count)} ${escapeHtml(t('commentsSignal'))}</span>`);
  if (task.workflow_template_id || task.current_step_key) signals.push(`<span class="card-hermes-signal workflow" title="${escapeHtml(task.workflow_template_id || '')}">↔ ${escapeHtml(task.current_step_key || task.workflow_template_id || 'workflow')}</span>`);
  if (reviewSignal) signals.push(`<span class="card-hermes-signal review">✓ ${escapeHtml(t('reviewSignal'))}</span>`);
  if (prSignal) signals.push(`<span class="card-hermes-signal pr">PR</span>`);
  return signals.join('');
}

const DONE_COLLAPSE_THRESHOLD = 8;
const DONE_ACTIVE_DOMINANCE_MULTIPLIER = 2;
const DONE_ARCHIVE_MODES = new Set(['collapsed', 'recent', 'all']);
const expandedEmptyStatuses = new Set();
let emptyColumnFocusDisabled = false;

function doneColumnModeKey(data) {
  return `kanbanDoneColumnMode:${data.board || 'default'}`;
}

function activeTaskCount(statuses, data) {
  return statuses
    .filter(status => !['done', 'archived'].includes(status))
    .reduce((sum, status) => sum + (data.columns[status] || []).length, 0);
}

function doneTasksDominateBoard(statuses, data) {
  const doneCount = (data.columns.done || []).length;
  const activeCount = activeTaskCount(statuses, data);
  return doneCount > DONE_COLLAPSE_THRESHOLD && doneCount > Math.max(activeCount * DONE_ACTIVE_DOMINANCE_MULTIPLIER, 0);
}

function getDoneArchiveMode(data) {
  try {
    const stored = localStorage.getItem(doneColumnModeKey(data));
    return DONE_ARCHIVE_MODES.has(stored) ? stored : 'collapsed';
  } catch (_err) {
    return 'collapsed';
  }
}

function setDoneArchiveMode(data, mode) {
  if (!DONE_ARCHIVE_MODES.has(mode)) return;
  try {
    localStorage.setItem(doneColumnModeKey(data), mode);
  } catch (_err) {
    // Storage can be unavailable in private/embedded contexts; the next render falls back safely.
  }
}

function doneArchiveAction(action, label, count = '') {
  return `<button type="button" class="button ghost" data-done-archive-action="${escapeHtml(action)}" aria-label="${escapeHtml(label)}"><span>${escapeHtml(label)}</span>${count !== '' ? `<strong>${escapeHtml(String(count))}</strong>` : ''}</button>`;
}

function doneArchiveSummary(doneTasks, mode) {
  const total = doneTasks.length;
  const visibleCount = mode === 'all' ? total : (mode === 'recent' ? Math.min(total, DONE_COLLAPSE_THRESHOLD) : 0);
  const countLabel = t('doneArchiveCount').replace('{count}', total).replace('{visible}', visibleCount);
  const actions = [
    mode !== 'recent' ? doneArchiveAction('recent', t('doneArchiveShowRecent'), Math.min(total, DONE_COLLAPSE_THRESHOLD)) : '',
    mode !== 'all' ? doneArchiveAction('all', t('doneArchiveShowAll'), total) : '',
    mode !== 'collapsed' ? doneArchiveAction('collapsed', t('doneArchiveHide')) : '',
  ].filter(Boolean).join('');
  return `<aside class="done-archive-summary" aria-label="${escapeHtml(t('doneArchiveCollapsed'))}">
    <div><strong>${escapeHtml(t('doneArchiveCollapsed'))}</strong><span>${escapeHtml(countLabel)}</span></div>
    <p>${escapeHtml(t('doneArchiveCollapsedHint'))}</p>
    <div class="done-archive-actions">${actions}</div>
  </aside>`;
}

function shouldFocusNonEmptyColumns(statuses, data) {
  const populatedStatuses = statuses.filter(status => (data.columns[status] || []).length > 0);
  const taskCount = populatedStatuses.reduce((sum, status) => sum + (data.columns[status] || []).length, 0);
  const emptyCount = statuses.length - populatedStatuses.length;
  return !emptyColumnFocusDisabled && taskCount > 0 && populatedStatuses.length <= 2 && emptyCount >= 3;
}

function emptyColumnDock(collapsedStatuses) {
  if (!collapsedStatuses.length) return '';
  const buttons = collapsedStatuses.map(status => {
    const statusLabel = escapeHtml(t(status));
    const revealLabel = escapeHtml(`${t('showColumn')}: ${t(status)}`);
    const addLabel = escapeHtml(`${t('addTaskToColumn')}: ${t(status)}`);
    return `<div class="collapsed-column-chip" data-collapsed-status="${escapeHtml(status)}">
      <button type="button" class="collapsed-column-reveal" data-reveal-column="${escapeHtml(status)}" aria-label="${revealLabel}"><span>${statusLabel}</span><strong>0</strong></button>
      <button type="button" class="mini-add" data-status="${escapeHtml(status)}" aria-label="${addLabel}" title="${addLabel}">＋</button>
    </div>`;
  }).join('');
  return `<aside class="empty-columns-dock" aria-label="${escapeHtml(t('collapsedEmptyColumns'))}">
    <div><strong>${escapeHtml(t('emptyColumnsCollapsed'))}</strong><span>${escapeHtml(t('emptyColumnsCollapsedHint'))}</span></div>
    <div class="collapsed-column-list">${buttons}</div>
  </aside>`;
}

function card(task) {
  const isUnassigned = !task.assignee;
  const assigneeHint = escapeHtml(t('profileMissing'));
  const safeStatus = safeStatusClass(task.status);
  const statusLabel = escapeHtml(t(task.status));
  const taskTitle = escapeHtml(task.title);
  const assigneeChip = task.assignee
    ? `<span>@${escapeHtml(task.assignee)}</span>`
    : `<span class="missing-assignee-chip" title="${assigneeHint}">⚠ ${assigneeHint}</span>`;
  const chips = [task.tenant, task.priority ? `P${task.priority}` : null].filter(Boolean);
  const parents = Number(task.link_counts?.parents || 0);
  const children = Number(task.link_counts?.children || 0);
  const progress = task.progress ? `<span>${task.progress.done}/${task.progress.total}</span>` : '';
  const workflow = task.workflow_template_id || task.current_step_key
    ? `<span class="workflow-chip" title="${escapeHtml(task.workflow_template_id || '')}">↔ ${escapeHtml(task.current_step_key || task.workflow_template_id || 'workflow')}</span>`
    : '';
  const signals = hermesSignals(task, parents, children);
  const taskId = escapeHtml(task.id);
  const childPortHint = escapeHtml(t('childPortHint'));
  const parentPortHint = escapeHtml(t('parentPortHint'));
  const cardAriaLabel = escapeHtml(`${t('openTaskHint')}: ${task.id} · ${t(task.status)} · ${task.title}`);
  const statusTitle = escapeHtml(`${t('taskStatusLabel')}: ${t(task.status)}`);
  return `<article class="task-card ${safeStatus}${isUnassigned ? ' is-unassigned' : ''}" data-task-id="${taskId}" data-parent-count="${parents}" data-child-count="${children}" data-assignee-state="${isUnassigned ? 'missing' : 'assigned'}" tabindex="0" aria-label="${cardAriaLabel}">
    <button type="button" class="dependency-port child-port" data-link-role="child" data-link-task-id="${taskId}" title="${childPortHint}" aria-label="${childPortHint}"><span>${escapeHtml(t('child'))}</span></button>
    <button type="button" class="dependency-port parent-port" data-link-role="parent" data-link-task-id="${taskId}" title="${parentPortHint}" aria-label="${parentPortHint}"><span>${escapeHtml(t('parent'))}</span></button>
    <div class="card-top card-primary-meta"><code>${taskId}</code>${isUnassigned ? `<span class="profile-missing-badge" title="${assigneeHint}" aria-label="${assigneeHint}">⚠ ${escapeHtml(t('profileMissingShort'))}</span>` : ''}<span class="task-status-pill ${safeStatus}" title="${statusTitle}" aria-label="${statusTitle}"><span class="status-dot ${safeStatus}"></span>${statusLabel}</span></div>
    <h3 class="task-card-title">${taskTitle}</h3>
    <div class="card-secondary-meta"><span>${assigneeChip}</span>${chips.map(x => `<span>${escapeHtml(x)}</span>`).join('')}${progress}${workflow}</div>
    ${signals ? `<div class="card-hermes-signals">${signals}</div>` : ''}
    ${task.body_preview ? `<p class="task-card-preview">${escapeHtml(task.body_preview)}</p>` : ''}
    <div class="card-foot"><span>💬 ${task.comment_count || 0}</span><span class="relation-badge" title="parents ${parents} · children ${children}">↑ ${parents} ↓ ${children}</span>${task.status === 'running' ? '<strong>LIVE</strong>' : ''}<span class="task-drag-hint" aria-hidden="true">↕ ${escapeHtml(t('dragTaskHint'))}</span></div>
  </article>`;
}

export function renderKpis(data) {
  const root = document.getElementById('kpiRow');
  const stats = data.stats?.by_status || {};
  const statuses = data.column_order || [];
  root.style.setProperty('--summary-chip-count', String(Math.max(1, statuses.length)));
  root.style.setProperty('--kpi-column-count', String(Math.max(1, statuses.length)));
  root.innerHTML = statuses.map(status => {
    const count = stats[status] || 0;
    return `<a class="summary-chip" href="#column-${escapeHtml(status)}" aria-label="${escapeHtml(`${t(status)}: ${count}`)}"><span>${escapeHtml(t(status))}</span><strong>${count}</strong></a>`;
  }).join('');
}

export function renderBoard(data) {
  const root = document.getElementById('board');
  const columnNav = document.getElementById('columnNav');
  const statuses = data.column_order || [];
  const focusEmptyColumns = shouldFocusNonEmptyColumns(statuses, data);
  const doneDominates = doneTasksDominateBoard(statuses, data);
  const doneMode = doneDominates ? getDoneArchiveMode(data) : 'all';
  const collapsedStatuses = focusEmptyColumns
    ? statuses.filter(status => !(data.columns[status] || []).length && !expandedEmptyStatuses.has(status))
    : [];
  const visibleStatuses = statuses.filter(status => !collapsedStatuses.includes(status));
  root.classList.toggle('is-focused-empty-columns', collapsedStatuses.length > 0);
  root.style.setProperty('--kanban-column-count', String(Math.max(1, visibleStatuses.length + (collapsedStatuses.length ? 1 : 0))));
  if (columnNav) {
    const navButtons = statuses.map((status, idx) => {
      const count = (data.columns[status] || []).length;
      const collapsed = collapsedStatuses.includes(status);
      const current = idx === 0 && !collapsed;
      return `<button type="button" class="column-nav-button${current ? ' active' : ''}${collapsed ? ' is-collapsed-empty' : ''}" data-column-target="${escapeHtml(status)}" data-column-collapsed="${collapsed ? 'true' : 'false'}" aria-current="${current ? 'true' : 'false'}"><span>${escapeHtml(t(status))}</span><strong>${count}</strong></button>`;
    }).join('');
    const toggle = collapsedStatuses.length
      ? `<button type="button" class="column-nav-button show-empty-columns" data-show-empty-columns><span>${escapeHtml(t('showEmptyColumns'))}</span><strong>${collapsedStatuses.length}</strong></button>`
      : (focusEmptyColumns || emptyColumnFocusDisabled ? `<button type="button" class="column-nav-button show-empty-columns" data-focus-empty-columns><span>${escapeHtml(t('focusNonEmptyColumns'))}</span></button>` : '');
    columnNav.innerHTML = navButtons + toggle;
    columnNav.querySelectorAll('[data-column-target]').forEach(button => {
      button.addEventListener('click', () => {
        const status = button.dataset.columnTarget;
        if (button.dataset.columnCollapsed === 'true') {
          expandedEmptyStatuses.add(status);
          renderBoard(data);
          requestAnimationFrame(() => document.getElementById(`column-${status}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' }));
          return;
        }
        const target = [...root.querySelectorAll('.board-column')].find(column => column.dataset.status === status);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
      });
    });
    columnNav.querySelector('[data-show-empty-columns]')?.addEventListener('click', () => {
      emptyColumnFocusDisabled = true;
      statuses.forEach(status => expandedEmptyStatuses.add(status));
      renderBoard(data);
    });
    columnNav.querySelector('[data-focus-empty-columns]')?.addEventListener('click', () => {
      emptyColumnFocusDisabled = false;
      expandedEmptyStatuses.clear();
      renderBoard(data);
    });
  }
  root.innerHTML = visibleStatuses.map(status => {
    const tasks = data.columns[status] || [];
    const doneTasks = status === 'done' ? tasks : [];
    const compactDone = status === 'done' && doneDominates;
    const renderedTasks = compactDone && doneMode !== 'all'
      ? (doneMode === 'recent' ? doneTasks.slice(0, DONE_COLLAPSE_THRESHOLD) : [])
      : tasks;
    const addLabel = escapeHtml(`${t('addTaskToColumn')}: ${t(status)}`);
    const emptyHint = escapeHtml(t('emptyColumnHint'));
    const archiveSummary = compactDone ? doneArchiveSummary(doneTasks, doneMode) : '';
    const emptyCard = status === 'done' && compactDone ? '' : `<div class="empty empty-column-card"><strong>${escapeHtml(t('empty'))}</strong><span>${emptyHint}</span></div>`;
    const cardsMarkup = renderedTasks.length ? renderedTasks.map(card).join('') : emptyCard;
    return `<section class="board-column${compactDone ? ' is-compact-done' : ''}" id="column-${escapeHtml(status)}" data-status="${escapeHtml(status)}" data-empty-column="${tasks.length ? 'false' : 'true'}" data-done-archive-mode="${compactDone ? escapeHtml(doneMode) : ''}">
      <header><div><h2>${escapeHtml(t(status))}</h2><small>${tasks.length}</small></div><button class="mini-add" data-status="${escapeHtml(status)}" aria-label="${addLabel}" title="${addLabel}">＋</button></header>
      <div class="drop-placeholder"></div>
      <div class="cards">${archiveSummary}${cardsMarkup}</div>
    </section>`;
  }).join('') + emptyColumnDock(collapsedStatuses);
  root.querySelectorAll('.task-card').forEach(el => {
    const open = () => {
      selectDependencyTask(el.dataset.taskId);
      openTaskDrawer(el.dataset.taskId);
    };
    el.addEventListener('mouseenter', () => focusDependencyTask(el.dataset.taskId));
    el.addEventListener('mouseleave', () => clearDependencyFocus(el.dataset.taskId));
    el.addEventListener('focus', () => focusDependencyTask(el.dataset.taskId));
    el.addEventListener('blur', () => clearDependencyFocus(el.dataset.taskId));
    el.addEventListener('click', open);
    el.addEventListener('keydown', ev => {
      if (ev.target !== el) return;
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        open();
      }
    });
  });
  root.querySelectorAll('[data-reveal-column]').forEach(btn => btn.addEventListener('click', () => {
    expandedEmptyStatuses.add(btn.dataset.revealColumn);
    renderBoard(data);
    requestAnimationFrame(() => document.getElementById(`column-${btn.dataset.revealColumn}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' }));
  }));
  root.querySelectorAll('[data-done-archive-action]').forEach(btn => btn.addEventListener('click', () => {
    setDoneArchiveMode(data, btn.dataset.doneArchiveAction);
    renderBoard(data);
    requestAnimationFrame(() => document.getElementById('column-done')?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' }));
  }));
  root.querySelectorAll('.mini-add').forEach(btn => btn.addEventListener('click', () => {
    document.dispatchEvent(new CustomEvent('kanban:open-task-create', { detail: { status: btn.dataset.status } }));
  }));
  attachDragHandlers(root);
  renderDependencyOverlay(data);
  updateColumnNavOnScroll(root, columnNav);
}

function updateColumnNavOnScroll(root, columnNav) {
  if (!root || !columnNav) return;
  const setActive = () => {
    const boardLeft = root.getBoundingClientRect().left;
    let active = null;
    let best = Number.POSITIVE_INFINITY;
    root.querySelectorAll('.board-column').forEach(column => {
      const distance = Math.abs(column.getBoundingClientRect().left - boardLeft);
      if (distance < best) {
        best = distance;
        active = column.dataset.status;
      }
    });
    if (!active) return;
    columnNav.querySelectorAll('[data-column-target]').forEach(button => {
      const selected = button.dataset.columnTarget === active;
      button.classList.toggle('active', selected);
      button.setAttribute('aria-current', selected ? 'true' : 'false');
    });
  };
  root.addEventListener('scroll', () => requestAnimationFrame(setActive), { passive: true });
  setActive();
}
