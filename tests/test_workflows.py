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
