import { api } from './api.js?v=20260506-01';
import { escapeHtml } from './markdown.js?v=20260506-01';
import { t } from './i18n.js?v=20260506-01';
import { state, toast, setBoard } from './state.js?v=20260506-01';

function stepKey(step) {
  return step.step_key || step.key || '';
}

function templateOptionLabel(template) {
  const count = template.step_count || (template.steps || []).length || 0;
  return `${template.name || template.id} · ${count} ${t('workflowSteps')}`;
}

function selectedWorkflowTemplate() {
  const select = document.getElementById('workflowTemplateSelect');
  const id = select?.value;
  return (state.workflowTemplates || []).find(template => template.id === id) || (state.workflowTemplates || [])[0];
}

function renderWorkflowSteps(root, steps, links = []) {
  const linkMap = new Map();
  for (const link of links || []) {
    const child = link.child_step || link.childStep;
    const parent = link.parent_step || link.parentStep;
    if (!child || !parent) continue;
    linkMap.set(child, [...(linkMap.get(child) || []), parent]);
  }
  const items = (steps || []).map(step => {
    const key = stepKey(step);
    const deps = step.depends_on || linkMap.get(key) || [];
    const assignee = step.assignee ? `@${step.assignee}` : t('unassigned');
    return `<li class="workflow-step ${escapeHtml(step.status || 'todo')}">
      <div><strong>${escapeHtml(step.title || key)}</strong><code>${escapeHtml(key)}</code></div>
      <div class="workflow-meta"><span>${escapeHtml(assignee)}</span><span>${escapeHtml(step.status || 'todo')}</span>${deps.length ? `<span>← ${deps.map(escapeHtml).join(', ')}</span>` : ''}</div>
    </li>`;
  }).join('');
  root.innerHTML = items ? `<ol class="workflow-step-list">${items}</ol>` : `<p class="muted">${t('empty')}</p>`;
}

function renderLocalWorkflowPreview() {
  const previewRoot = document.getElementById('workflowPreview');
  const template = selectedWorkflowTemplate();
  if (!previewRoot || !template) return;
  const steps = (template.steps || []).map(step => ({
    ...step,
    step_key: step.key,
    status: (step.depends_on || []).length ? 'todo' : (step.status || 'ready')
  }));
  renderWorkflowSteps(previewRoot, steps, []);
}

export function populateWorkflowTemplateSelect() {
  const select = document.getElementById('workflowTemplateSelect');
  if (!select) return;
  const previous = select.value;
  select.replaceChildren();
  for (const template of state.workflowTemplates || []) {
    const option = document.createElement('option');
    option.value = template.id;
    option.textContent = templateOptionLabel(template);
    select.appendChild(option);
  }
  if (previous && [...select.options].some(option => option.value === previous)) select.value = previous;
  renderLocalWorkflowPreview();
}

async function previewWorkflowFromForm(form) {
  const previewRoot = document.getElementById('workflowPreview');
  const data = new FormData(form);
  const title = String(data.get('title') || '').trim();
  if (!title) {
    renderLocalWorkflowPreview();
    return;
  }
  previewRoot.innerHTML = `<p class="muted">${escapeHtml(t('loading'))}</p>`;
  const preview = await api.workflowPreview(state.board, {
    template_id: String(data.get('template_id') || ''),
    title,
    body: String(data.get('body') || '')
  });
  renderWorkflowSteps(previewRoot, preview.steps || [], preview.links || []);
}

export function setupWorkflowDialog(load) {
  const workflowDialog = document.getElementById('workflowDialog');
  const workflowForm = document.getElementById('workflowForm');
  const workflowBtn = document.getElementById('workflowBtn');
  const workflowTemplateSelect = document.getElementById('workflowTemplateSelect');
  if (!workflowDialog || !workflowForm || !workflowBtn || !workflowTemplateSelect) return;

  workflowBtn.addEventListener('click', () => {
    populateWorkflowTemplateSelect();
    workflowDialog.showModal();
  });
  workflowForm.querySelector('[data-workflow-cancel]').addEventListener('click', () => workflowDialog.close());
  workflowTemplateSelect.addEventListener('change', renderLocalWorkflowPreview);
  workflowForm.querySelector('[data-workflow-preview]').addEventListener('click', async () => {
    try {
      await previewWorkflowFromForm(workflowForm);
    } catch (err) {
      toast(err.message || String(err), 'error');
    }
  });
  workflowForm.addEventListener('submit', async ev => {
    ev.preventDefault();
    const form = new FormData(ev.currentTarget);
    const title = String(form.get('title') || '').trim();
    if (!title) return;
    const payload = {
      template_id: String(form.get('template_id') || ''),
      title,
      body: String(form.get('body') || ''),
      instance_id: String(form.get('instance_id') || '').trim() || null
    };
    const result = await api.instantiateWorkflow(state.board, payload);
    workflowDialog.close();
    ev.currentTarget.reset();
    toast(`${result.created} ${t('createdToast')} · ${result.existing} existing`);
    await load();
  });
}

export function setupForms(load) {
  document.getElementById('quickCreateForm').addEventListener('submit', async ev => {
    ev.preventDefault();
    const form = new FormData(ev.currentTarget);
    const title = String(form.get('title') || '').trim();
    if (!title) return;
    const payload = { title, assignee: form.get('assignee') || null, status: form.get('status') || 'ready' };
    localStorage.setItem('lastAssignee', payload.assignee || '');
    await api.createTask(state.board, payload);
    ev.currentTarget.reset();
    document.getElementById('quickAssignee').value = localStorage.getItem('lastAssignee') || '';
    toast('created');
    await load();
  });

  const boardDialog = document.getElementById('boardDialog');
  document.getElementById('newBoardBtn').addEventListener('click', () => boardDialog.showModal());
  document.getElementById('boardForm').addEventListener('submit', async ev => {
    ev.preventDefault();
    const form = Object.fromEntries(new FormData(ev.currentTarget));
    if (!form.slug) return;
    const data = await api.createBoard({ ...form, switch: true });
    setBoard(data.current);
    boardDialog.close();
    toast('board created');
    await load();
  });

  const bulkDialog = document.getElementById('bulkDialog');
  document.getElementById('bulkBtn').addEventListener('click', () => bulkDialog.showModal());
  document.getElementById('bulkForm').addEventListener('submit', async ev => {
    ev.preventDefault();
    const lines = new FormData(ev.currentTarget).get('lines');
    const data = await api.bulkCreate(state.board, { lines });
    bulkDialog.close();
    toast(`${data.created} created`);
    await load();
  });

  setupWorkflowDialog(load);
}
