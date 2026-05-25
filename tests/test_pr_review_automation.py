from __future__ import annotations

PR_URL = 'https://github.com/daily-language-3mins/HermesKanban/pull/123'


def _create(client, title='Implement feature', **extra):
    response = client.post('/api/tasks', json={'title': title, 'assignee': 'implementer', **extra})
    assert response.status_code == 200, response.text
    return response.json()['task']['id']


def _detail(client, task_id):
    response = client.get(f'/api/tasks/{task_id}')
    assert response.status_code == 200, response.text
    return response.json()


def _children(client, task_id):
    return _detail(client, task_id)['links']['children']


def _review_children(client, task_id):
    return [child for child in _children(client, task_id) if _detail(client, child)['task']['assignee'] == 'reviewer']


def test_complete_with_metadata_pr_url_creates_reviewer_task(client):
    task_id = _create(client, 'Implement issue 41')

    completed = client.post(f'/api/tasks/{task_id}/complete', json={'metadata': {'pr_url': PR_URL}, 'summary': 'PR opened'})

    assert completed.status_code == 200, completed.text
    assert completed.json()['results'][0]['ok'] is True
    review_ids = _review_children(client, task_id)
    assert len(review_ids) == 1
    review = _detail(client, review_ids[0])['task']
    assert review['status'] == 'ready'
    assert review['assignee'] == 'reviewer'
    assert review['idempotency_key'] == f'auto-pr-review:{task_id}:{PR_URL}'
    assert PR_URL in review['body']
    assert 'LGTM' in review['body']
    assert 'self-approval' in review['body']
    assert 'GitHub' in review['body'] and 'comment' in review['body']
    assert 'review_status' in review['body']
    assert 'passed|changes_needed|unable_to_review' in review['body']
    assert 'github_review_url' in review['body'] or 'github_comment_url' in review['body']


def test_auto_created_reviewer_task_requires_github_auth_preflight_before_local_review(client):
    task_id = _create(client, 'Implement issue 54')

    completed = client.post(f'/api/tasks/{task_id}/complete', json={'metadata': {'pr_url': PR_URL}, 'summary': 'PR opened'})

    assert completed.status_code == 200, completed.text
    review = _detail(client, _review_children(client, task_id)[0])['task']
    body = review['body']
    assert './scripts/hermes-kanban github-auth-preflight' in body
    assert 'gh auth status' in body
    assert 'gh auth login' in body
    assert 'GH_TOKEN' in body
    assert 'GITHUB_TOKEN' in body
    assert 'GitHub PR review posting is blocked' in body
    assert body.index('github-auth-preflight') < body.index('Read the PR body')


def test_auto_review_task_names_actionable_profile_auth_preflight_before_review_work(client):
    task_id = _create(client, 'Implement issue 60')

    completed = client.post(f'/api/tasks/{task_id}/complete', json={'metadata': {'pr_url': PR_URL}, 'summary': 'PR opened'})

    assert completed.status_code == 200, completed.text
    review = _detail(client, _review_children(client, task_id)[0])['task']
    body = review['body']
    assert 'gh auth status' in body
    assert f'gh pr view {PR_URL} --json url,number,headRefName,baseRefName' in body
    assert 'gh auth setup-git' in body
    assert 'GH_TOKEN' in body
    assert 'GITHUB_TOKEN' in body
    assert 'reviewer profile' in body
    assert 'unable_to_review' in body
    assert 'raw HTTP auth headers' not in body
    assert body.index('gh auth status') < body.index('Read the PR body')


def test_complete_with_summary_or_comment_pr_url_creates_reviewer_task(client):
    summary_task = _create(client, 'Implement summary PR detection')
    completed = client.post(f'/api/tasks/{summary_task}/complete', json={'summary': f'Opened {PR_URL}.'})
    assert completed.status_code == 200, completed.text
    assert len(_review_children(client, summary_task)) == 1

    comment_task = _create(client, 'Implement comment PR detection')
    commented = client.post(
        f'/api/tasks/{comment_task}/comments',
        json={'author': 'implementer', 'body': f'review-required handoff: {PR_URL})'},
    )
    assert commented.status_code == 200, commented.text
    completed = client.post(f'/api/tasks/{comment_task}/complete', json={'summary': 'handoff in comment'})
    assert completed.status_code == 200, completed.text
    review_ids = _review_children(client, comment_task)
    assert len(review_ids) == 1
    assert _detail(client, review_ids[0])['task']['body'].count(PR_URL) >= 1


def test_auto_review_creation_is_idempotent(client):
    from kanban_webui.hermes_imports import kanban_db
    from kanban_webui.pr_review_automation import reconcile_pr_review_tasks

    task_id = _create(client, 'Implement idempotent PR detection')
    completed = client.post(f'/api/tasks/{task_id}/complete', json={'metadata': {'pr_url': PR_URL}})
    assert completed.status_code == 200, completed.text

    conn = kanban_db.connect()
    try:
        first = reconcile_pr_review_tasks(conn, task_ids=[task_id])
        second = reconcile_pr_review_tasks(conn, task_ids=[task_id])
    finally:
        conn.close()

    review_ids = _review_children(client, task_id)
    assert len(review_ids) == 1
    assert first[0]['task_id'] == review_ids[0]
    assert second[0]['task_id'] == review_ids[0]
    assert second[0]['created'] is False


def test_no_recursive_review_task_for_reviewer_completion(client):
    reviewer_task = _create(client, 'Review PR 123', assignee='reviewer')

    completed = client.post(f'/api/tasks/{reviewer_task}/complete', json={'summary': f'LGTM {PR_URL}', 'metadata': {'pr_url': PR_URL, 'review_status': 'passed'}})

    assert completed.status_code == 200, completed.text
    assert _children(client, reviewer_task) == []


def test_reviewer_completion_metadata_surfaces_review_status(client):
    task_id = _create(client, 'Review PR 123', assignee='reviewer')
    metadata = {
        'review_status': 'passed',
        'pr_url': PR_URL,
        'github_comment_url': 'https://github.com/daily-language-3mins/HermesKanban/pull/123#issuecomment-1',
        'tests_run': ['uv run --extra test pytest -q'],
    }

    completed = client.post(f'/api/tasks/{task_id}/complete', json={'summary': 'LGTM', 'metadata': metadata})

    assert completed.status_code == 200, completed.text
    detail = _detail(client, task_id)
    run_metadata = detail['runs'][-1]['metadata']
    assert run_metadata == metadata
    assert run_metadata['review_status'] == 'passed'


def test_reviewer_completion_requires_github_evidence_for_auto_review_task(client):
    source = _create(client, 'Implement review evidence enforcement')
    completed = client.post(f'/api/tasks/{source}/complete', json={'metadata': {'pr_url': PR_URL}})
    assert completed.status_code == 200, completed.text
    review_task = _review_children(client, source)[0]

    missing_evidence = client.post(
        f'/api/tasks/{review_task}/complete',
        json={'summary': 'LGTM', 'metadata': {'review_status': 'passed', 'pr_url': PR_URL}},
    )
    assert missing_evidence.status_code == 400
    assert 'github_review_url or github_comment_url' in missing_evidence.text

    with_evidence = client.post(
        f'/api/tasks/{review_task}/complete',
        json={
            'summary': 'LGTM',
            'metadata': {
                'review_status': 'passed',
                'pr_url': PR_URL,
                'github_comment_url': 'https://github.com/daily-language-3mins/HermesKanban/pull/123#issuecomment-1',
            },
        },
    )
    assert with_evidence.status_code == 200, with_evidence.text


def test_bulk_done_transition_with_pr_url_creates_reviewer_task(client):
    task_id = _create(client, 'Implement via bulk')

    bulk = client.post('/api/tasks/bulk', json={'ids': [task_id], 'status': 'done', 'summary': f'Opened {PR_URL}'})

    assert bulk.status_code == 200, bulk.text
    assert bulk.json()['results'][0]['ok'] is True
    assert len(_review_children(client, task_id)) == 1
