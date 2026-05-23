from __future__ import annotations


def _create_task(client, title: str, *, status: str = 'todo', priority: int = 0) -> str:
    response = client.post('/api/tasks', json={'title': title, 'status': status, 'priority': priority})
    assert response.status_code == 200, response.text
    return response.json()['task']['id']


def _column_ids(client, status: str) -> list[str]:
    response = client.get('/api/board')
    assert response.status_code == 200, response.text
    return [task['id'] for task in response.json()['columns'][status]]


def test_same_column_reorder_persists_across_board_reload(client):
    first = _create_task(client, 'first', priority=30)
    middle = _create_task(client, 'middle', priority=20)
    last = _create_task(client, 'last', priority=10)
    assert _column_ids(client, 'todo') == [first, middle, last]

    moved = client.post(f'/api/tasks/{middle}/reorder', json={'status': 'todo', 'before_id': first})
    assert moved.status_code == 200, moved.text
    assert 'rank' in moved.json()

    assert _column_ids(client, 'todo') == [middle, first, last]
    assert _column_ids(client, 'todo') == [middle, first, last]


def test_reorder_to_bottom_persists_across_board_reload(client):
    first = _create_task(client, 'first', priority=30)
    middle = _create_task(client, 'middle', priority=20)
    last = _create_task(client, 'last', priority=10)
    assert _column_ids(client, 'todo') == [first, middle, last]

    moved = client.post(f'/api/tasks/{first}/reorder', json={'status': 'todo', 'after_id': last})
    assert moved.status_code == 200, moved.text

    assert _column_ids(client, 'todo') == [middle, last, first]
    assert _column_ids(client, 'todo') == [middle, last, first]


def test_cross_column_reorder_sets_target_position(client):
    triage = _create_task(client, 'triage-card', status='triage', priority=1)
    ready_top = _create_task(client, 'ready-top', status='ready', priority=30)
    ready_bottom = _create_task(client, 'ready-bottom', status='ready', priority=10)
    assert _column_ids(client, 'ready') == [ready_top, ready_bottom]

    moved = client.post(f'/api/tasks/{triage}/reorder', json={'status': 'ready', 'before_id': ready_top})
    assert moved.status_code == 200, moved.text
    assert moved.json()['task']['status'] == 'ready'

    assert _column_ids(client, 'ready') == [triage, ready_top, ready_bottom]
    assert _column_ids(client, 'ready') == [triage, ready_top, ready_bottom]


def test_cross_column_reorder_can_archive_without_breaking_existing_drag_flow(client):
    task_id = _create_task(client, 'archive-me', status='ready')
    completed = client.post(f'/api/tasks/{task_id}/reorder', json={'status': 'done', 'summary': 'complete', 'result': 'complete'})
    assert completed.status_code == 200, completed.text

    archived = client.post(f'/api/tasks/{task_id}/reorder', json={'status': 'archived'})
    assert archived.status_code == 200, archived.text
    assert archived.json()['task']['status'] == 'archived'

    response = client.get('/api/board?include_archived=true')
    assert response.status_code == 200, response.text
    assert [task['id'] for task in response.json()['columns']['archived']] == [task_id]


def test_reorder_to_blocked_requires_block_reason(client):
    task_id = _create_task(client, 'needs-context', status='ready')

    missing_reason = client.post(f'/api/tasks/{task_id}/reorder', json={'status': 'blocked'})
    assert missing_reason.status_code == 400, missing_reason.text
    assert 'block_reason' in missing_reason.text

    blocked = client.post(
        f'/api/tasks/{task_id}/reorder',
        json={'status': 'blocked', 'block_reason': 'waiting for dependency'},
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()['task']['status'] == 'blocked'
