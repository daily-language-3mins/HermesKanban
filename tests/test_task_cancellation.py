from __future__ import annotations


def _create(client, title: str, **extra) -> str:
    response = client.post('/api/tasks', json={'title': title, **extra})
    assert response.status_code == 200, response.text
    return response.json()['task']['id']


def _claim(client, task_id: str) -> dict:
    response = client.post(f'/api/tasks/{task_id}/claim', json={'claimer': 'test-host:worker'})
    assert response.status_code == 200, response.text
    return response.json()


def test_cancel_requires_explicit_confirmation(client):
    task_id = _create(client, 'Cancel confirmation guard')
    _claim(client, task_id)

    response = client.post(f'/api/tasks/{task_id}/cancel', json={'reason': 'operator request'})

    assert response.status_code == 400
    assert 'confirm=cancel' in response.text
    task = client.get(f'/api/tasks/{task_id}').json()['task']
    assert task['status'] == 'running'


def test_cancel_nonexistent_task_returns_404(client):
    response = client.post('/api/tasks/not-a-task/cancel', params={'confirm': 'cancel'}, json={'reason': 'cleanup'})

    assert response.status_code == 404


def test_cancel_non_running_task_returns_409(client):
    task_id = _create(client, 'Not running cancel target')

    response = client.post(f'/api/tasks/{task_id}/cancel', params={'confirm': 'cancel'}, json={'reason': 'no-op'})

    assert response.status_code == 409
    assert 'not running' in response.text
    task = client.get(f'/api/tasks/{task_id}').json()['task']
    assert task['status'] == 'ready'


def test_cancel_running_task_reclaims_claim_and_records_state(client):
    task_id = _create(client, 'Running cancellation target')
    claimed = _claim(client, task_id)
    run_id = claimed['run']['id']

    response = client.post(
        f'/api/tasks/{task_id}/cancel',
        params={'confirm': 'cancel'},
        json={'reason': 'operator stopped bad run'},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data['ok'] is True
    assert data['action'] == 'cancelled'
    assert data['semantics'] == 'reclaimed_claim_no_webui_pid_kill'
    assert data['active_run'] is None
    assert data['task']['status'] == 'ready'
    assert data['task']['claim_lock'] is None
    assert data['task']['claim_expires'] is None
    assert data['task']['current_run_id'] is None

    closed_run = next(run for run in data['runs'] if run['id'] == run_id)
    assert closed_run['status'] == 'reclaimed'
    assert closed_run['outcome'] == 'reclaimed'
    assert closed_run['ended_at'] is not None
    assert 'operator stopped bad run' in closed_run['error']
    assert closed_run['metadata']['termination_attempted'] is False

    assert data['last_event']['kind'] == 'reclaimed'
    assert data['last_event']['run_id'] == run_id
    assert data['last_event']['payload']['manual'] is True
    assert data['last_event']['payload']['reason'] == 'operator stopped bad run'

    detail = client.get(f'/api/tasks/{task_id}').json()
    assert detail['task']['status'] == 'ready'
    assert detail['runs'][-1]['outcome'] == 'reclaimed'
    assert detail['events'][-1]['kind'] == 'reclaimed'


def test_reclaim_alias_uses_same_confirmed_cancel_semantics(client):
    task_id = _create(client, 'Running reclaim alias target')
    _claim(client, task_id)

    response = client.post(
        f'/api/tasks/{task_id}/reclaim',
        params={'confirm': 'cancel'},
        json={'reason': 'alias smoke'},
    )

    assert response.status_code == 200, response.text
    assert response.json()['task']['status'] == 'ready'
