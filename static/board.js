import { t } from './i18n.js?v=20260505-9';
import { escapeHtml } from './markdown.js?v=20260505-9';
import { openTaskDrawer } from './drawer.js?v=20260505-9';
import { attachDragHandlers } from './dragdrop.js?v=20260505-9';
import { clearDependencyFocus, focusDependencyTask, renderDependencyOverlay, selectDependencyTask } from './dependency-lines.js?v=20260505-9';

function card(task) {
  const chips = [task.assignee ? `@${task.assignee}` : 'unassigned', task.tenant, task.priority ? `P${task.priority}` : null].filter(Boolean);
  const parents = Number(task.link_counts?.parents || 0);
  const children = Number(task.link_counts?.children || 0);
  const progress = task.progress ? `<span>${task.progress.done}/${task.progress.total}</span>` : '';
  return `<article class="task-card ${task.status}" data-task-id="${escapeHtml(task.id)}" data-parent-count="${parents}" data-child-count="${children}" tabindex="0">
    <div class="card-top"><code>${escapeHtml(task.id)}</code><span class="status-dot ${task.status}"></span></div>
    <h3>${escapeHtml(task.title)}</h3>
    ${task.body_preview ? `<p>${escapeHtml(task.body_preview)}</p>` : ''}
    <div class="chips">${chips.map(x => `<span>${escapeHtml(x)}</span>`).join('')}${progress}</div>
    <div class="card-foot"><span>💬 ${task.comment_count || 0}</span><span class="relation-badge" title="parents ${parents} · children ${children}">↑ ${parents} ↓ ${children}</span>${task.status === 'running' ? '<strong>LIVE</strong>' : ''}</div>
  </article>`;
}

export function renderKpis(data) {
  const root = document.getElementById('kpiRow');
  const stats = data.stats?.by_status || {};
  root.innerHTML = data.column_order.map(status => `<div class="kpi"><small>${t(status)}</small><strong>${stats[status] || 0}</strong></div>`).join('');
}

export function renderBoard(data) {
  const root = document.getElementById('board');
  root.innerHTML = data.column_order.map(status => {
    const tasks = data.columns[status] || [];
    return `<section class="board-column" data-status="${status}">
      <header><div><h2>${t(status)}</h2><small>${tasks.length}</small></div><button class="mini-add" data-status="${status}">＋</button></header>
      <div class="drop-placeholder"></div>
      <div class="cards">${tasks.length ? tasks.map(card).join('') : `<div class="empty">${t('empty')}</div>`}</div>
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
    el.addEventListener('keydown', ev => { if (ev.key === 'Enter') open(); });
  });
  root.querySelectorAll('.mini-add').forEach(btn => btn.addEventListener('click', () => {
    document.getElementById('quickStatus').value = btn.dataset.status;
    document.getElementById('quickTitle').focus();
  }));
  attachDragHandlers(root);
  renderDependencyOverlay(data);
}
