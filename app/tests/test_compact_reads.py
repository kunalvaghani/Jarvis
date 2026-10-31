"""Compact reads (control.compact_reads): drop only nameless containers and repeated names; keep every fact and ref."""
from pathlib import Path
import re

import pytest

from jarvis.control.compact import compact

READS = Path(__file__).resolve().parent / 'fixtures' / 'control_reads'
REF = re.compile(r'\[((?:ref|u)_?\d+)\]')
NODE = re.compile(r'^ *(\w[\w ]*?) "([^"]*)"(.*)$')


def kept_facts(read):
    """Every named node or text with its ref: what the planner can read or act on."""
    facts = set()
    for line in read.split('\n'):
        match = NODE.match(line)
        if match and match[2]:
            facts.add((match[1], match[2], tuple(REF.findall(match[3]))))
    return facts


@pytest.mark.parametrize('name', ['herokuapp-tables.txt', 'calculator.txt'])
def test_recorded_reads_lose_no_named_node(name):
    read = (READS / name).read_text(encoding='utf-8')
    short = compact(read)
    assert len(short) < len(read)
    lost = kept_facts(read) - kept_facts(short)
    # Only a text/image line that repeats its parent's name may go.
    assert all(role in ('text', 'image') for role, _, _ in lost), lost


def test_table_answer_survives_and_page_shrinks():
    read = (READS / 'herokuapp-tables.txt').read_text(encoding='utf-8')
    short = compact(read)
    for needle in ('heading "Data Tables" [ref_8]', 'columnheader "Email" [ref_17]', 'cell "Smith" [ref_22]',
                   'text "No Class or ID attributes'):
        assert needle in short
    assert 'generic ""' not in short and 'paragraph ""' not in short and 'rowgroup ""' not in short
    assert len(short) <= .7 * len(read)


def test_children_of_dropped_containers_move_up_and_keep_order():
    read = '\n'.join([
        'RootWebArea "Page" [ref_1]',
        '  generic "" [ref_2]',
        '    generic "" [ref_3]',
        '      button "Save" [ref_4]',
        '    heading "Title" [ref_5]',
        '      text "Title"',
        '      text "Subtitle"',
        '  link "Home" [ref_6]',
        '    image "Home" [ref_7]',
        '    image "Logo" [ref_8]',
    ])
    assert compact(read) == '\n'.join([
        'RootWebArea "Page" [ref_1]',
        '  button "Save" [ref_4]',
        '  heading "Title" [ref_5]',
        '    text "Subtitle"',
        '  link "Home" [ref_6]',
        '    image "Logo" [ref_8]',
    ])


@pytest.mark.parametrize('line', ['generic "" focused [ref_2]', 'group "" checked [ref_2]', "Custom \"\" [u2] value='7'",
                                  'Group "" [u3] selected'])
def test_containers_with_state_are_kept(line):
    assert compact('Window "W" [u1]\n  ' + line + '\n    Button "OK" [u9]') == \
        'Window "W" [u1]\n  ' + line + '\n    Button "OK" [u9]'


def test_named_containers_and_non_node_lines_are_kept():
    read = 'Group "Memory controls" [u16]\n  Button "MC" [u17]\n[truncated: scope the read with filter or ref]\n'
    assert compact(read) == read
    assert compact('') == ''


def test_service_compacts_only_with_the_flag(tmp_path):
    from jarvis.control import settings as control_settings
    from jarvis.control.service import ControlService
    from jarvis.control.types import ActionResult
    read = (READS / 'herokuapp-tables.txt').read_text(encoding='utf-8')
    from jarvis.control.types import Route
    result = ActionResult('a1', True, Route.BROWSER, verified=True)
    off = ControlService(control_settings.load(tmp_path, {}))
    on = ControlService(control_settings.load(tmp_path, {'control': {'compact_reads': True}}))
    assert off._report(result, read).endswith(read[:9000])
    assert on._report(result, read).endswith(compact(read))
    assert ControlService(control_settings.load(tmp_path, {'control': {'compact_reads': 'yes'}}))._report(result, read) \
        == off._report(result, read)
