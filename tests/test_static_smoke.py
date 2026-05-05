from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


def test_static_shell_contains_required_ui_contracts(client):
    index = client.get('/').text
    assert 'Hermes KanbanWebUI' in index
    assert 'langToggle' in index
    assert 'boardSelect' in index
    assert 'quickCreateForm' in index
    assert '/static/app.js' in index

    root = Path(__file__).resolve().parents[1]
    for rel in ['static/app.js', 'static/board.js', 'static/drawer.js', 'static/monitor.js', 'static/i18n.js', 'static/design-tokens.css', 'DESIGN.md']:
        assert (root / rel).is_file(), rel


def test_static_javascript_parses():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is required for static JavaScript syntax checks')
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root / 'static').glob('*.js')):
        subprocess.run([node, '--check', str(path)], check=True, cwd=root)


def test_dragdrop_pointer_contract_strings():
    root = Path(__file__).resolve().parents[1]
    dragdrop = (root / 'static' / 'dragdrop.js').read_text(encoding='utf-8')
    for phrase in ['pointerdown', 'setPointerCapture', 'drag threshold', 'drop placeholder', 'autoScrollBoard', 'moveTask']:
        assert phrase in dragdrop


def test_drawer_matches_dashboard_detail_controls():
    root = Path(__file__).resolve().parents[1]
    drawer = (root / 'static' / 'drawer.js').read_text(encoding='utf-8')
    api = (root / 'static' / 'api.js').read_text(encoding='utf-8')

    for phrase in [
        'data-action="triage"',
        'data-action="unblock"',
        'data-assignee-save',
        'data-priority-save',
        'bodyEditForm',
        'addParentSelect',
        'addChildSelect',
        'data-link-action',
        'data-home-platform',
        'workerLogContent',
    ]:
        assert phrase in drawer

    for phrase in ['homeChannels', 'subscribeHome', 'unsubscribeHome', 'linkTask', 'unlinkTask', 'taskLog']:
        assert phrase in api


def test_button_hover_keeps_ghost_text_readable():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert '.button.primary, .button:hover' not in style
    assert '.button.ghost { background: rgba(255,255,255,0.72); color: var(--ink); }' in style
    assert '.button.ghost:hover { background: rgba(23,23,23,.06); color: var(--ink); border-color: var(--border); }' in style
    assert '.button.ghost.danger-btn:hover' in style


def test_drawer_forms_do_not_overflow_grid_tracks():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'grid-template-columns: minmax(0, 1fr) minmax(0, .8fr) minmax(96px, .4fr) auto' in style
    assert 'minmax(220px, 1fr)' not in style
    assert '.inline-form label, .dependency-form { display: grid; gap: 6px; color: var(--muted); font-weight: 700; min-width: 0; }' in style
    assert '.inline-form input, .inline-form select, .dependency-form select, .dependency-form button { width: 100%; min-width: 0; }' in style
    assert '.dependency-grid > div { min-width: 0; }' in style


def test_dependency_visual_options_and_focus_overlay_contract():
    root = Path(__file__).resolve().parents[1]
    index = (root / 'static' / 'index.html').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    board = (root / 'static' / 'board.js').read_text(encoding='utf-8')
    lines = (root / 'static' / 'dependency-lines.js').read_text(encoding='utf-8')
    drawer = (root / 'static' / 'drawer.js').read_text(encoding='utf-8')
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert 'id="dependencyView"' in index
    for mode in ['focus', 'all', 'blocked', 'off']:
        assert f'value="{mode}"' in index
    assert 'setupDependencyControls' in app
    assert 'renderDependencyOverlay' in board
    assert 'data-parent-count' in board
    assert 'data-child-count' in board
    for phrase in ['dependency-overlay', 'dependency-edge', 'dependency-focus', 'dependency-dim', 'dependency-blocked']:
        assert phrase in lines
        assert phrase in style
    assert 'dependency-mini-map' in drawer
    assert 'dependencyMiniMap' in drawer


def test_dependency_lines_render_above_column_backgrounds_below_cards():
    root = Path(__file__).resolve().parents[1]
    style = (root / 'static' / 'style.css').read_text(encoding='utf-8')

    assert '.board-column { position: relative; width: var(--column-width);' in style
    assert '.board-column { position: relative; z-index: 1;' not in style
    assert '.cards { position: relative; z-index: 2;' in style
    assert '.task-card { position: relative;' in style
    assert '.dependency-overlay { position: absolute; left: 0; top: 0; z-index: 1;' in style


def test_dependency_edges_fan_out_shared_endpoints():
    root = Path(__file__).resolve().parents[1]
    lines = (root / 'static' / 'dependency-lines.js').read_text(encoding='utf-8')

    for phrase in [
        'assignEdgePorts',
        'sourceOffset',
        'targetOffset',
        'portOffset',
        'data-source-offset',
        'data-target-offset',
    ]:
        assert phrase in lines
