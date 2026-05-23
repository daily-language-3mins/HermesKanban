from __future__ import annotations


def test_versioned_static_assets_are_cacheable_and_validated(client):
    response = client.get('/static/app.js?v=20260522-zh-tw')

    assert response.status_code == 200
    assert response.headers['cache-control'] == 'public, max-age=31536000, immutable'
    assert response.headers.get('etag')


def test_spa_shell_and_unversioned_static_assets_are_not_immutable(client):
    shell = client.get('/')
    unversioned = client.get('/static/app.js')

    assert shell.status_code == 200
    assert unversioned.status_code == 200
    assert shell.headers.get('cache-control') != 'public, max-age=31536000, immutable'
    assert unversioned.headers.get('cache-control') != 'public, max-age=31536000, immutable'


def test_api_responses_are_compressed_when_client_supports_gzip(client):
    client.post(
        '/api/tasks',
        json={
            'title': 'Large response task',
            'assignee': 'perf',
            'body': 'gzip me ' * 300,
        },
    )
    response = client.get('/api/board?board=default', headers={'Accept-Encoding': 'gzip'})

    assert response.status_code == 200
    assert response.headers['content-encoding'] == 'gzip'
    assert response.headers.get('vary') == 'Accept-Encoding'
    assert 'tasks' in response.json()


def test_api_responses_are_marked_dynamic_not_immutable(client):
    response = client.get('/api/boards')

    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
