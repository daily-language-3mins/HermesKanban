import { api } from './api.js?v=20260522-zh-tw';
import { state, toast } from './state.js?v=20260522-zh-tw';

let draggedId = null;

function cardsContainer(column) {
  return column.querySelector('.cards') || column;
}

function dropPlaceholder(column) {
  return column.querySelector('.drop-placeholder');
}

function taskIdFromElement(element) {
  return element && element.classList.contains('task-card') ? element.dataset.taskId : null;
}

function draggableCards(container) {
  return [...container.querySelectorAll('.task-card:not(.drag-ghost)')].filter(card => card.dataset.taskId !== draggedId);
}

function placeDropPlaceholder(column, clientY) {
  const container = cardsContainer(column);
  const placeholder = dropPlaceholder(column);
  if (!container || !placeholder) return { before_id: null, after_id: null };

  const cards = draggableCards(container);
  let beforeCard = null;
  for (const card of cards) {
    const rect = card.getBoundingClientRect();
    if (clientY < rect.top + rect.height / 2) {
      beforeCard = card;
      break;
    }
  }

  if (beforeCard) {
    container.insertBefore(placeholder, beforeCard);
  } else {
    container.appendChild(placeholder);
  }

  const previousCard = placeholder.previousElementSibling && placeholder.previousElementSibling.classList.contains('task-card')
    ? placeholder.previousElementSibling
    : null;
  const nextCard = placeholder.nextElementSibling && placeholder.nextElementSibling.classList.contains('task-card')
    ? placeholder.nextElementSibling
    : null;

  return {
    before_id: taskIdFromElement(nextCard),
    after_id: taskIdFromElement(previousCard)
  };
}

function placementFromPlaceholder(column) {
  const placeholder = dropPlaceholder(column);
  if (!placeholder) return { before_id: null, after_id: null };
  const previousCard = placeholder.previousElementSibling && placeholder.previousElementSibling.classList.contains('task-card')
    ? placeholder.previousElementSibling
    : null;
  const nextCard = placeholder.nextElementSibling && placeholder.nextElementSibling.classList.contains('task-card')
    ? placeholder.nextElementSibling
    : null;
  return {
    before_id: taskIdFromElement(nextCard),
    after_id: taskIdFromElement(previousCard)
  };
}

export function attachDragHandlers(root) {
  root.querySelectorAll('.task-card').forEach(card => {
    card.draggable = true;
    card.addEventListener('dragstart', ev => {
      if (ev.target.closest('.dependency-port')) {
        ev.preventDefault();
        return;
      }
      draggedId = card.dataset.taskId;
      ev.dataTransfer.effectAllowed = 'move';
      ev.dataTransfer.setData('text/plain', draggedId);
      card.classList.add('drag-ghost');
    });
    card.addEventListener('dragend', () => card.classList.remove('drag-ghost'));

    // Pointer Events contract for touch/pen hardening: pointer capture, drag threshold
    // ghost card, drop placeholder, and auto-scroll hooks. HTML5 DnD
    // is the MVP transport; these hooks keep the implementation ready for the
    // full Trello-like pointer engine without changing board.js.
    card.addEventListener('pointerdown', ev => {
      card._pointerStart = { x: ev.clientX, y: ev.clientY, id: ev.pointerId };
      if (card.setPointerCapture) card.setPointerCapture(ev.pointerId);
    });
    card.addEventListener('pointermove', ev => {
      if (!card._pointerStart) return;
      const dx = Math.abs(ev.clientX - card._pointerStart.x);
      const dy = Math.abs(ev.clientY - card._pointerStart.y);
      if (dx + dy > 12) card.classList.add('pointer-drag-ready');
      autoScrollBoard(ev.clientX);
    });
    card.addEventListener('pointerup', ev => {
      if (card.releasePointerCapture && card._pointerStart) card.releasePointerCapture(ev.pointerId);
      card._pointerStart = null;
      card.classList.remove('pointer-drag-ready');
    });
  });

  root.querySelectorAll('.board-column').forEach(column => {
    column.addEventListener('dragover', ev => {
      ev.preventDefault();
      column.classList.add('drop-target');
      placeDropPlaceholder(column, ev.clientY);
    });
    column.addEventListener('dragleave', ev => {
      if (!column.contains(ev.relatedTarget)) column.classList.remove('drop-target');
    });
    column.addEventListener('drop', async ev => {
      ev.preventDefault();
      column.classList.remove('drop-target');
      const taskId = ev.dataTransfer.getData('text/plain') || draggedId;
      if (!taskId) return;
      const placement = placementFromPlaceholder(column);
      await moveTask(taskId, column.dataset.status, placement);
    });
  });
}

export function autoScrollBoard(clientX) {
  const board = document.getElementById('board');
  if (!board) return;
  const rect = board.getBoundingClientRect();
  if (clientX > rect.right - 80) board.scrollLeft += 16;
  if (clientX < rect.left + 80) board.scrollLeft -= 16;
}

export async function moveTask(taskId, status, placement = {}) {
  const payload = {
    status,
    before_id: placement.before_id || null,
    after_id: placement.after_id || null
  };
  if (status === 'blocked') payload.block_reason = prompt('Block reason?') || '';
  if (status === 'done') {
    const summary = prompt('Completion summary?') || '';
    payload.summary = summary;
    payload.result = summary;
  }
  if (status === 'archived') {
    if (!confirm('Archive this task?')) return;
    await api.updateTask(state.board, taskId, { status });
  } else {
    await api.reorderTask(state.board, taskId, payload);
  }
  toast(`moved ${taskId} → ${status}`);
  document.dispatchEvent(new CustomEvent('kanban:refresh'));
}
