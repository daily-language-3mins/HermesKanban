from __future__ import annotations


def _workflow_payload(**overrides):
    payload = {
        'template_id': 'dev-plan-implement-review-v1',
        'title': 'Workflow UI',
        'body': 'Build workflow support with tests.',
        'instance_id': 'wf_test_001',
    }
    payload.update(overrides)
    return payload


def test_workflow_templates_endpoint_exposes_builtin_steps(client):
    response = client.get('/api/workflows/templates')

    assert response.status_code == 200, response.text
    data = response.json()
    template = next(t for t in data['templates'] if t['id'] == 'dev-plan-implement-review-v1')
    assert template['name']
    assert template['step_count'] == 3
    assert [step['key'] for step in template['steps']] == ['plan', 'implement', 'review']
    assert template['steps'][0]['assignee'] == 'dev_plan'
    assert template['steps'][1]['depends_on'] == ['plan']


def test_workflow_preview_does_not_create_tasks(client):
    response = client.post('/api/workflows/preview', json=_workflow_payload(instance_id='ignored'))

    assert response.status_code == 200, response.text
    data = response.json()
    assert data['template_id'] == 'dev-plan-implement-review-v1'
    assert data['instance_id'] == 'preview'
    assert [step['step_key'] for step in data['steps']] == ['plan', 'implement', 'review']
    assert data['steps'][0]['status'] == 'ready'
    assert data['steps'][1]['status'] == 'todo'
    assert data['steps'][2]['status'] == 'todo'
    assert data['links'] == [
        {'parent_step': 'plan', 'child_step': 'implement'},
        {'parent_step': 'implement', 'child_step': 'review'},
    ]
    assert client.get('/api/board').json()['tasks'] == []


def test_workflow_instantiate_creates_idempotent_linked_step_tasks(client):
    first = client.post('/api/workflows/instantiate', json=_workflow_payload())

    assert first.status_code == 200, first.text
    data = first.json()
    assert data['ok'] is True
    assert data['created'] == 3
    assert data['existing'] == 0
    assert data['instance_id'] == 'wf_test_001'
    assert [step['step_key'] for step in data['tasks']] == ['plan', 'implement', 'review']

    tasks_by_step = {step['step_key']: step for step in data['tasks']}
    board = client.get('/api/board').json()
    assert len(board['tasks']) == 3
    assert {'parent_id': tasks_by_step['plan']['task_id'], 'child_id': tasks_by_step['implement']['task_id']} in board['links']
    assert {'parent_id': tasks_by_step['implement']['task_id'], 'child_id': tasks_by_step['review']['task_id']} in board['links']

    for step_key, item in tasks_by_step.items():
        task = client.get(f"/api/tasks/{item['task_id']}").json()['task']
        assert task['workflow_template_id'] == 'dev-plan-implement-review-v1'
        assert task['current_step_key'] == step_key
        assert task['idempotency_key'] == f'workflow:wf_test_001:{step_key}'
        assert task['title'].startswith({'plan': '기획:', 'implement': '구현:', 'review': '리뷰:'}[step_key])

    claimed = client.post(f"/api/tasks/{tasks_by_step['plan']['task_id']}/claim", json={'claimer': 'tester'})
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()['run']['step_key'] == 'plan'

    second = client.post('/api/workflows/instantiate', json=_workflow_payload())
    assert second.status_code == 200, second.text
    duplicate = second.json()
    assert duplicate['created'] == 0
    assert duplicate['existing'] == 3
    assert [step['task_id'] for step in duplicate['tasks']] == [step['task_id'] for step in data['tasks']]


def test_workflow_instance_endpoint_groups_tasks_and_links(client):
    created = client.post('/api/workflows/instantiate', json=_workflow_payload(instance_id='wf_test_group')).json()

    response = client.get('/api/workflows/instances/wf_test_group')

    assert response.status_code == 200, response.text
    data = response.json()
    assert data['instance_id'] == 'wf_test_group'
    assert data['template_id'] == 'dev-plan-implement-review-v1'
    assert data['progress'] == {'done': 0, 'total': 3}
    assert [task['current_step_key'] for task in data['tasks']] == ['plan', 'implement', 'review']
    assert data['links'] == [
        {
            'parent_step': 'plan',
            'child_step': 'implement',
            'parent_id': created['tasks'][0]['task_id'],
            'child_id': created['tasks'][1]['task_id'],
        },
        {
            'parent_step': 'implement',
            'child_step': 'review',
            'parent_id': created['tasks'][1]['task_id'],
            'child_id': created['tasks'][2]['task_id'],
        },
    ]


def test_task_create_accepts_workflow_fields(client):
    response = client.post(
        '/api/tasks',
        json={
            'title': 'Manual workflow step',
            'workflow_template_id': 'manual-template',
            'current_step_key': 'manual-step',
            'idempotency_key': 'workflow:manual:manual-step',
            'status': 'triage',
        },
    )

    assert response.status_code == 200, response.text
    task = response.json()['task']
    assert task['workflow_template_id'] == 'manual-template'
    assert task['current_step_key'] == 'manual-step'
    assert task['status'] == 'triage'
