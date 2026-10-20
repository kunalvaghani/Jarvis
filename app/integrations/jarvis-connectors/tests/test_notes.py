"""Notes child: the starter's safety tests, ported onto BaseConnector + ConfinedRoot."""
from types import SimpleNamespace

import pytest

from conftest import load_connector
from jarvis_connector import ToolError

NotesConnector = load_connector('notes', 'NotesConnector')


@pytest.fixture
def notes(tmp_path):
    (tmp_path / 'a.md').write_text('Hello from Jarvis\n', encoding='utf-8')
    (tmp_path / 'b.md').write_text('Blender workflow note\n', encoding='utf-8')
    (tmp_path / 'notallowed.txt').write_text('private', encoding='utf-8')
    (tmp_path / 'big.md').write_text('x' * (64 * 1024 + 1), encoding='utf-8')
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'hidden.md').write_text('Blender in a subfolder', encoding='utf-8')
    connector = NotesConnector()
    connector.configure(SimpleNamespace(root=str(tmp_path)))
    return connector


def test_listing_skips_other_types_oversized_and_subfolders(notes):
    assert notes.invoke('list_notes', {}) == ['a.md', 'b.md']
    assert notes.invoke('list_notes', {'limit': 1}) == ['a.md']


def test_read(notes):
    assert notes.invoke('read_note', {'filename': 'a.md'}) == {
        'filename': 'a.md', 'content': 'Hello from Jarvis\n', 'truncated': False}


def test_search(notes):
    found = notes.invoke('search_notes', {'query': 'blender'})
    assert [row['filename'] for row in found] == ['b.md']
    assert [row['filename'] for row in notes.invoke('search_notes', {'query': 'NOTE blender'})] == ['b.md']
    assert notes.invoke('search_notes', {'query': 'blender jarvis'}) == []  # every word must appear


@pytest.mark.parametrize('filename', ['../secret.md', '..\\secret.md', 'C:\\temp\\secret.md', 'sub/hidden.md',
                                      'a.txt', 'notallowed.txt', '', '.', '..', 'missing.md', 'big.md', 'a.md\0'])
def test_traversal_and_disallowed_files_blocked(notes, filename):
    with pytest.raises(ToolError):
        notes.invoke('read_note', {'filename': filename})


def test_hard_limits(notes):
    for name, arguments in [('list_notes', {'limit': 101}), ('list_notes', {'limit': 0}),
                            ('search_notes', {'query': ''}), ('search_notes', {'query': '   '}),
                            ('search_notes', {'query': 'x' * 121}), ('search_notes', {'query': 'a', 'max_results': 51})]:
        with pytest.raises(ToolError):
            notes.invoke(name, arguments)


def test_no_symlinks(notes, tmp_path):
    try:
        (tmp_path / 'link.md').symlink_to(tmp_path / 'a.md')
    except OSError:
        pytest.skip('OS disallows symlink creation')
    assert 'link.md' not in notes.invoke('list_notes', {})
    with pytest.raises(ToolError):
        notes.invoke('read_note', {'filename': 'link.md'})


def test_relative_or_missing_root_is_a_tool_error(tmp_path):
    for root in ['relative\\notes', str(tmp_path / 'missing'), '']:
        connector = NotesConnector()
        connector.configure(SimpleNamespace(root=root))
        assert connector.call('list_notes', {})['isError'] is True


def test_template_write_tool_creates_once_and_verifies(tmp_path):
    Example = load_connector('template', 'ExampleConnector')
    connector = Example(allow_write=True)
    connector.configure(SimpleNamespace(workspace=str(tmp_path)))
    assert connector.invoke('create_text_file', {'filename': 'hello.txt', 'text': 'hi'}) == {
        'filename': 'hello.txt', 'characters': 2}
    with pytest.raises(ToolError):
        connector.invoke('create_text_file', {'filename': 'hello.txt', 'text': 'overwrite?'})
    assert (tmp_path / 'hello.txt').read_text(encoding='utf-8') == 'hi'
