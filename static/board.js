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
  root.style.setProperty('--kanban-column-count', String(Math.max(1, statuses.length)));
  if (columnNav) {
    columnNav.innerHTML = statuses.map((status, idx) => {
      const count = (data.columns[status] || []).length;
      return `<button type="button" class="column-nav-button${idx === 0 ? ' active' : ''}" data-column-target="${status}" aria-current="${idx === 0 ? 'true' : 'false'}"><span>${t(status)}</span><strong>${count}</strong></button>`;
    }).join('');
    columnNav.querySelectorAll('[data-column-target]').forEach(button => {
      button.addEventListener('click', () => {
        const target = [...root.querySelectorAll('.board-column')].find(column => column.dataset.status === button.dataset.columnTarget);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
      });
    });
  }
  root.innerHTML = statuses.map(status => {
    const tasks = data.columns[status] || [];
    const addLabel = escapeHtml(`${t('addTaskToColumn')}: ${t(status)}`);
    const emptyHint = escapeHtml(t('emptyColumnHint'));
    return `<section class="board-column" id="column-${escapeHtml(status)}" data-status="${status}">
      <header><div><h2>${t(status)}</h2><small>${tasks.length}</small></div><button class="mini-add" data-status="${status}" aria-label="${addLabel}" title="${addLabel}">＋</button></header>
      <div class="drop-placeholder"></div>
      <div class="cards">${tasks.length ? tasks.map(card).join('') : `<div class="empty empty-column-card"><strong>${t('empty')}</strong><span>${emptyHint}</span></div>`}</div>
    </section>`;
  }).join('');
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
