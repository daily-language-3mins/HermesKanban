from __future__ import annotations


PROMPT_WORKFLOW_SOURCE = 'prompt-generated-v1'


def test_workflow_instance_endpoint_groups_prompt_generated_tasks(client):
    parent = client.post(
        '/api/tasks',
        json={
            'title': '기획: prompt workflow',
            'workflow_template_id': PROMPT_WORKFLOW_SOURCE,
            'current_step_key': 'plan',
            'idempotency_key': 'workflow:wf_prompt_manual:plan',
            'status': 'ready',
        },
    )
    assert parent.status_code == 200, parent.text
    parent_task = parent.json()['task']

    child = client.post(
        '/api/tasks',
        json={
            'title': '구현: prompt workflow',
            'workflow_template_id': PROMPT_WORKFLOW_SOURCE,
            'current_step_key': 'implement',
            'idempotency_key': 'workflow:wf_prompt_manual:implement',
            'parents': [parent_task['id']],
        },
    )
    assert child.status_code == 200, child.text
    child_task = child.json()['task']

    response = client.get('/api/workflows/instances/wf_prompt_manual')

    assert response.status_code == 200, response.text
    data = response.json()
    assert data['instance_id'] == 'wf_prompt_manual'
    assert data['template_id'] == PROMPT_WORKFLOW_SOURCE
    assert data['progress'] == {'done': 0, 'total': 2}
    assert [task['current_step_key'] for task in data['tasks']] == ['plan', 'implement']
    assert data['links'] == [
        {
            'parent_step': 'plan',
            'child_step': 'implement',
            'parent_id': parent_task['id'],
            'child_id': child_task['id'],
        }
    ]


def test_task_create_accepts_workflow_fields(client):
    response = client.post(
        '/api/tasks',
        json={
            'title': 'Manual workflow step',
            'workflow_template_id': 'manual-source',
            'current_step_key': 'manual-step',
            'idempotency_key': 'workflow:manual:manual-step',
            'status': 'triage',
        },
    )

    assert response.status_code == 200, response.text
    task = response.json()['task']
    assert task['workflow_template_id'] == 'manual-source'
    assert task['current_step_key'] == 'manual-step'
    assert task['status'] == 'triage'


def test_bulk_create_tasks_preserves_workflow_fields(client):
    response = client.post(
        '/api/tasks/bulk-create',
        json={
            'tasks': [
                {
                    'title': 'Bulk explicit workflow step',
                    'workflow_template_id': 'bulk-source',
                    'current_step_key': 'bulk-step',
                    'status': 'triage',
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()['results'][0]
    assert result['ok'] is True
    assert response.json()['created'] == 1
    task = client.get(f"/api/tasks/{result['task_id']}").json()['task']
    assert task['workflow_template_id'] == 'bulk-source'
    assert task['current_step_key'] == 'bulk-step'
    assert task['status'] == 'triage'


def test_bulk_create_lines_preserves_default_workflow_fields(client):
    response = client.post(
        '/api/tasks/bulk-create',
        json={
            'lines': 'Bulk line workflow step',
            'defaults': {
                'workflow_template_id': 'line-default-source',
                'current_step_key': 'line-default-step',
                'status': 'ready',
            },
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()['results'][0]
    assert result['ok'] is True
    assert response.json()['created'] == 1
    task = client.get(f"/api/tasks/{result['task_id']}").json()['task']
    assert task['workflow_template_id'] == 'line-default-source'
    assert task['current_step_key'] == 'line-default-step'
    assert task['status'] == 'ready'


def test_bulk_create_reports_workflow_field_errors_per_item(client, monkeypatch):
    from kanban_webui import kanban_api

    original = kanban_api._apply_create_workflow_fields

    def fail_for_error_step(conn, task_id, *, workflow_template_id, current_step_key):
        if current_step_key == 'error-step':
            raise RuntimeError('workflow metadata failed')
        original(
            conn,
            task_id,
            workflow_template_id=workflow_template_id,
            current_step_key=current_step_key,
        )

    monkeypatch.setattr(kanban_api, '_apply_create_workflow_fields', fail_for_error_step)

    response = client.post(
        '/api/tasks/bulk-create',
        json={
            'tasks': [
                {
                    'title': 'Bulk workflow ok',
                    'workflow_template_id': 'bulk-source',
                    'current_step_key': 'ok-step',
                },
                {
                    'title': 'Bulk workflow error',
                    'workflow_template_id': 'bulk-source',
                    'current_step_key': 'error-step',
                },
            ]
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data['created'] == 1
    assert data['results'][0]['ok'] is True
    assert data['results'][1]['ok'] is False
    assert data['results'][1]['title'] == 'Bulk workflow error'
    assert 'workflow metadata failed' in data['results'][1]['error']
    ok_task = client.get(f"/api/tasks/{data['results'][0]['task_id']}").json()['task']
    assert ok_task['current_step_key'] == 'ok-step'
