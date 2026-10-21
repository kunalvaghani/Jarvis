"""Phase 2: API/code-first execution strategy, real adapters and safe fallback.

REAL: openpyxl/python-docx (.venv-skills), pypdf, background Blender, native Excel
(new hidden instance), a disposable Win32 UIA window, headless Chrome DOM, the
real ToolRegistry/event log. MOCK (labelled per test): planner Brain shell,
adapter handlers that simulate outages, pointer user32 calls.
Software that is not installed makes a test skip with an explicit BLOCKED reason.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid
import zipfile

import pytest

from jarvis import app_adapters, execution_strategy as strategy
from jarvis.execution_contracts import read_outcomes
from jarvis.toolkits import ToolUnavailable
from jarvis.tools import ToolRegistry

BASE = Path(__file__).resolve().parents[1]
SKILLS = BASE / '.venv-skills' / 'Scripts' / 'python.exe'
from jarvis.blender_installation import executables as blender_installations
BLENDER = next(iter(blender_installations(r'D:\Blender\blender.exe')), Path(r'D:\Blender\blender.exe'))


def skills(code, *args):
    if not SKILLS.is_file():
        pytest.skip('BLOCKED: .venv-skills is not installed.')
    subprocess.run([str(SKILLS), '-c', code, *map(str, args)], check=True, timeout=120)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def env(tmp_path):
    folder = tmp_path / 'docs'
    folder.mkdir()
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    approvals = []
    actions = SimpleNamespace(base=runtime, allowed_tools=None, report=Mock(), task_state=None,
                              config={'execution_strategy': {'blender_executable': str(BLENDER),
                                                             'unreal_engine_root': r'D:\UE_5.8'}},
                              _task_folder=lambda name, cancelled: str(folder),
                              _approve=lambda kind, detail, cancelled: approvals.append((kind, json.loads(detail))))
    return SimpleNamespace(actions=actions, folder=folder, runtime=runtime, approvals=approvals,
                           registry=ToolRegistry(actions))


def call(env, tool, value, **content):
    result = env.registry.execute({'action': tool, 'value': value, 'folder': 'docs',
                                   'content': json.dumps(content)}, lambda: False)
    return json.loads(result.evidence)


def workbook(path, chart=False):
    skills("import openpyxl,sys\n"
           "b=openpyxl.Workbook();s=b.active;s.title='Data';s['A1']=2;s['A2']=3;s['A3']='=A1*A2';s['B1']='label'\n"
           "o=b.create_sheet('Other');o['C3']='=SUM(Data!A1:A2)'\n"
           + ("from openpyxl.chart import BarChart,Reference\nc=BarChart();c.add_data(Reference(s,min_col=1,min_row=1,max_row=2));s.add_chart(c,'E2')\n" if chart else "")
           + "b.save(sys.argv[1])", path)


# ---- 1. XLSX: values and formulas survive (REAL openpyxl) -----------------------------------------------------------
def test_P02_01_xlsx_write_preserves_formulas_and_other_cells(env):
    path = env.folder / 'budget.xlsx'
    workbook(path)
    result = call(env, 'office_xlsx', 'budget.xlsx', operation='write', sheet='Data', cells={'A1': 10, 'B2': '=A3+1'})
    assert result['verification'] == 'verified' and 'unchanged' in result['evidence']
    data = call(env, 'office_xlsx', 'budget.xlsx', operation='read')
    cells = data['cells']
    assert cells['Data']['A1']['value'] == 10 and cells['Data']['B2']['formula'] == '=A3+1'
    assert cells['Data']['A3']['formula'] == '=A1*A2' and cells['Other']['C3']['formula'] == '=SUM(Data!A1:A2)'
    assert cells['Data']['B1']['value'] == 'label'
    backups = list((env.runtime / '.jarvis-runtime/backups/documents').iterdir())
    assert len(backups) == 1 and env.approvals[0][0] == 'office_xlsx'
    assert not list(env.folder.glob('.jarvis-*'))  # temporary copies cleaned up


def test_P02_01b_unknown_sheet_and_bad_cells_change_nothing(env):
    path = env.folder / 'budget.xlsx'
    workbook(path)
    before = sha(path)
    with pytest.raises(ValueError, match='Unknown worksheet'):
        call(env, 'office_xlsx', 'budget.xlsx', operation='write', sheet='Nope', cells={'A1': 1})
    from jarvis.tools import ToolArgumentError
    with pytest.raises((ValueError, ToolArgumentError)):
        call(env, 'office_xlsx', 'budget.xlsx', operation='write', sheet='Data', cells={'1A': 1})
    assert sha(path) == before and env.approvals == []


# ---- 7. API refused -> structured fallback (REAL openpyxl refusal + REAL Excel) -------------------------------------
def excel_available():
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'Excel.Application'))
        return True
    except OSError:
        return False


def test_P02_07_chart_workbook_falls_back_to_native_excel_and_keeps_chart(env):
    if not excel_available():
        pytest.skip('BLOCKED: Microsoft Excel automation is not installed.')
    path = env.folder / 'charted.xlsx'
    workbook(path, chart=True)
    assert 'charts' in app_adapters.package_features(path)
    result = json.loads(env.registry.execute({'action': 'strategy_execute', 'value': 'charted.xlsx', 'folder': 'docs',
        'content': json.dumps({'operation': 'write', 'sheet': 'Data', 'cells': {'A2': 7}})}, lambda: False).evidence)
    assert result['method'] == 'xlsx.excel_com' and result['tier'] == 'structured'
    # Feature detection excludes openpyxl at planning time, so no API attempt is even made.
    assert result['attempts'] == [{'method': 'xlsx.excel_com', 'status': 'completed'}]
    explained = json.loads(env.registry.execute({'action': 'execution_methods', 'value': 'charted.xlsx', 'folder': 'docs',
        'content': json.dumps({'operation': 'write'})}, lambda: False).evidence)
    api = next(c for c in explained['candidates'] if c['method'] == 'xlsx.openpyxl')
    assert not api['eligible'] and 'cannot preserve charts, drawings' in api['reasons']
    assert result['result']['verification'] == 'verified' and result['result']['office_instance'] in {'exited', 'terminated'}
    assert 'charts' in app_adapters.package_features(path)  # Excel saved the chart part
    data = call(env, 'office_xlsx', 'charted.xlsx', operation='read')
    assert data['cells']['Data']['A2']['value'] == 7 and data['cells']['Data']['A3']['formula'] == '=A1*A2'
    assert data['cells']['Data']['A3']['value'] == 14  # Excel recalculated and cached the value
    rows = [r for r in read_outcomes(env.runtime) if r.get('adapter') == 'xlsx.excel_com']
    assert rows and rows[-1]['verification'] == 'verified' and rows[-1]['method_tier'] == 'structured'


def test_P02_07b_plan_selects_structured_when_api_cannot_preserve_features(env):
    request = strategy.request_for('charted.xlsx', 'write', features=('charts',))
    plan = strategy.plan(env.actions, request)
    by_id = {c['method']: c for c in plan.candidates}
    assert not by_id['xlsx.openpyxl']['eligible'] and 'cannot preserve charts' in by_id['xlsx.openpyxl']['reasons']
    if excel_available():
        assert plan.selected == 'xlsx.excel_com'
    assert plan.gui_fallback == 'xlsx.gui' and plan.idempotency == 'non_idempotent' and plan.max_attempts == 1


def test_P02_07c_simulated_api_outage_falls_back_only_before_dispatch(env):
    """MOCK handlers: an outage before input falls back; a post-dispatch failure stops (no replay)."""
    workbook(env.folder / 'a.xlsx')
    calls = []

    def unavailable(actions, step, cancelled):
        calls.append(step['action'])
        raise ToolUnavailable('simulated API outage before any input')

    def structured(actions, step, cancelled):
        calls.append(step['action'])
        return json.dumps({'method': 'xlsx.excel_com', 'verification': 'verified'})

    with patch.dict(app_adapters.HANDLERS, {'office_xlsx': unavailable, 'office_automation': structured}), \
            patch.object(strategy, '_requirement', return_value=True):
        result = json.loads(env.registry.execute({'action': 'strategy_execute', 'value': 'a.xlsx', 'folder': 'docs',
            'content': json.dumps({'operation': 'write', 'sheet': 'Data', 'cells': {'A1': 1}})}, lambda: False).evidence)
    assert calls == ['office_xlsx', 'office_automation'] and result['method'] == 'xlsx.excel_com'

    calls.clear()

    def uncertain(actions, step, cancelled):
        calls.append(step['action'])
        raise ValueError('write outcome uncertain after dispatch')

    with patch.dict(app_adapters.HANDLERS, {'office_xlsx': uncertain, 'office_automation': structured}), \
            patch.object(strategy, '_requirement', return_value=True):
        with pytest.raises(ValueError, match='uncertain'):
            env.registry.execute({'action': 'strategy_execute', 'value': 'a.xlsx', 'folder': 'docs',
                'content': json.dumps({'operation': 'write', 'sheet': 'Data', 'cells': {'A1': 1}})}, lambda: False)
    assert calls == ['office_xlsx']  # never replayed through another method


def test_P02_07d_all_methods_unavailable_reports_gui_fallback_without_acting(env):
    workbook(env.folder / 'a.xlsx')
    with patch.object(strategy, '_requirement', return_value=False):
        with pytest.raises(ToolUnavailable, match='GUI fallback from a fresh observation: xlsx.gui'):
            env.registry.execute({'action': 'strategy_execute', 'value': 'a.xlsx', 'folder': 'docs',
                'content': json.dumps({'operation': 'write', 'sheet': 'Data', 'cells': {'A1': 1}})}, lambda: False)
    assert env.actions._strategy_exhausted == {'a.xlsx'}


def test_P02_07e_read_only_retry_is_bounded_and_writes_are_single_attempt(env):
    """MOCK handler: transient OSError on a read retries once; never for writes."""
    workbook(env.folder / 'r.xlsx')
    calls = []

    def flaky(actions, step, cancelled):
        calls.append(json.loads(step['content'])['operation'])
        raise OSError('transient')

    with patch.dict(app_adapters.HANDLERS, {'office_xlsx': flaky}), patch.object(strategy, '_requirement', return_value=True):
        for operation, expected in (('read', 2), ('write', 1)):
            calls.clear()
            with pytest.raises(OSError):
                env.registry.execute({'action': 'strategy_execute', 'value': 'r.xlsx', 'folder': 'docs',
                    'content': json.dumps({'operation': operation, 'sheet': 'Data', 'cells': {'A1': 1}})}, lambda: False)
            assert len(calls) == expected


# ---- 2. DOCX: structure verified (REAL python-docx) ------------------------------------------------------------------
def document(path):
    skills("import docx,sys\nd=docx.Document();d.add_heading('Report',1);d.add_paragraph('Status: draft');"
           "t=d.add_table(rows=2,cols=2);t.cell(0,0).text='Owner';t.cell(0,1).text='TBD';d.save(sys.argv[1])", path)


def test_P02_02_docx_edits_verify_structure(env):
    document(env.folder / 'report.docx')
    result = call(env, 'office_docx', 'report.docx', operation='write', edits=[
        {'kind': 'replace_text', 'find': 'draft', 'replace': 'final'},
        {'kind': 'append_paragraph', 'text': 'Approved by the fixture.'},
        {'kind': 'set_table_cell', 'table': 0, 'row': 0, 'column': 1, 'text': 'Jarvis'}])
    assert result['verification'] == 'verified'
    data = call(env, 'office_docx', 'report.docx', operation='read')
    texts = [p['text'] for p in data['paragraphs']]
    assert texts[:2] == ['Report', 'Status: final'] and texts[-1] == 'Approved by the fixture.'
    assert data['paragraphs'][0]['style'] == 'Heading 1' and data['tables'] == [[['Owner', 'Jarvis'], ['', '']]]


def test_P02_02b_tracked_changes_and_signatures_refuse_api_write(env):
    path = env.folder / 'tracked.docx'
    document(path)
    with zipfile.ZipFile(path) as source:
        parts = {name: source.read(name) for name in source.namelist()}
    parts['word/document.xml'] = parts['word/document.xml'].replace(b'<w:body>', b'<w:body><w:ins w:id="1" w:author="x"/>', 1)
    parts['_xmlsignatures/sig1.xml'] = b'<Signature/>'
    with zipfile.ZipFile(path, 'w') as target:
        for name, data in parts.items():
            target.writestr(name, data)
    before = sha(path)
    with pytest.raises(ToolUnavailable, match='signatures, tracked_changes'):
        call(env, 'office_docx', 'tracked.docx', operation='write', edits=[{'kind': 'append_paragraph', 'text': 'x'}])
    assert sha(path) == before and env.approvals == []


def test_P02_02c_native_word_edit_on_temporary_copy(env):
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'Word.Application'))
    except OSError:
        pytest.skip('BLOCKED: Microsoft Word automation is not installed.')
    document(env.folder / 'native.docx')
    result = call(env, 'office_automation', 'native.docx', operation='write', edits=[
        {'kind': 'replace_text', 'find': 'draft', 'replace': 'reviewed'},
        {'kind': 'append_paragraph', 'text': 'Native Word appended this.'}])
    assert result['method'] == 'docx.word_com' and result['verification'] == 'verified'
    assert result['office_instance'] in {'exited', 'terminated'}
    texts = [p['text'] for p in call(env, 'office_docx', 'native.docx', operation='read')['paragraphs']]
    assert 'Status: reviewed' in texts and texts[-1] == 'Native Word appended this.'
    assert env.approvals[0][1]['application'] == 'Word'


# ---- 3. PDF (REAL pypdf; fixture text rendered with reportlab in .venv-skills) ---------------------------------------
def pdf(path, pages):
    skills("from reportlab.pdfgen import canvas;import sys\nc=canvas.Canvas(sys.argv[1])\n"
           "for i in range(int(sys.argv[2])):\n c.drawString(72,720,'Fixture page %d'%(i+1));c.showPage()\nc.save()", path, pages)


def test_P02_03_pdf_text_and_new_file_composition(env):
    pdf(env.folder / 'a.pdf', 3)
    pdf(env.folder / 'b.pdf', 2)
    text = call(env, 'pdf_document', 'a.pdf', operation='text', pages=[2])
    assert 'Fixture page 2' in text['text']['2'] and text['pages'] == 3
    before = (sha(env.folder / 'a.pdf'), sha(env.folder / 'b.pdf'))
    result = call(env, 'pdf_document', 'a.pdf', operation='compose', output='merged.pdf',
                  sources=[{'path': 'a.pdf', 'pages': [1, 3], 'rotate': 90}, {'path': 'b.pdf'}])
    assert result['pages'] == 4 and result['verification'] == 'verified'
    assert (sha(env.folder / 'a.pdf'), sha(env.folder / 'b.pdf')) == before  # sources untouched
    from pypdf import PdfReader
    reader = PdfReader(env.folder / 'merged.pdf')
    assert [p.rotation for p in reader.pages] == [90, 90, 0, 0]
    assert 'Fixture page 3' in reader.pages[1].extract_text()
    with pytest.raises(ValueError, match='never overwritten'):
        call(env, 'pdf_document', 'a.pdf', operation='compose', output='merged.pdf', sources=[{'path': 'a.pdf'}])


# ---- 4. Blender (REAL background Blender) ------------------------------------------------------------------------------
def test_P02_04_blender_creates_verified_disposable_scene(env):
    if not BLENDER.is_file():
        pytest.skip('BLOCKED: Blender is not installed at the configured path.')
    result = call(env, 'blender_task', 'scene.blend', operation='create',
                  objects=[{'type': 'cube', 'name': 'Crate', 'location': [1, 2, 3]},
                           {'type': 'torus', 'name': 'Ring', 'scale': [2, 2, 2]}],
                  export={'format': 'gltf', 'path': 'scene.glb'})
    assert result['verification'] == 'verified' and result['export'] == 'scene.glb'
    names = {row['name']: row for row in result['objects']}
    assert names['Crate']['vertices'] == 8 and names['Crate']['location'] == [1.0, 2.0, 3.0]
    assert names['Ring']['scale'] == [2.0, 2.0, 2.0]
    assert (env.folder / 'scene.glb').read_bytes()[:4] == b'glTF'
    inspected = call(env, 'blender_task', 'scene.blend', operation='inspect')
    assert {row['name'] for row in inspected['objects']} == {'Crate', 'Ring'}
    with pytest.raises(ValueError, match='never overwritten'):
        call(env, 'blender_task', 'scene.blend', operation='create', objects=[{'type': 'cube', 'name': 'X'}])


def test_P02_04b_blender_rejects_code_and_bad_arguments_before_launch(env):
    for objects in ([{'type': 'cube; import os', 'name': 'X'}], [{'type': 'cube', 'name': '__import__("os")'}],
                    [{'type': 'cube', 'name': 'X', 'location': [1, 2]}], [{'type': 'cube', 'name': 'X', 'script': 'x'}]):
        with pytest.raises(ValueError):
            call(env, 'blender_task', 'bad.blend', operation='create', objects=objects)
    assert env.approvals == [] and not (env.folder / 'bad.blend').exists()


# ---- Unreal and VS Code (REAL read-only) -------------------------------------------------------------------------------
def test_P02_unreal_manifest_is_read_only(env):
    if not Path(r'D:\UE_5.8\Engine\Build\Build.version').is_file():
        pytest.skip('BLOCKED: Unreal Engine 5.8 manifest not present.')
    result = json.loads(env.registry.execute({'action': 'unreal_task', 'value': 'inspect'}, lambda: False).evidence)
    assert result['version'].startswith('5.8') and result['editor_cmd_available'] is True
    assert 'not enabled' in result['editor_python']


def test_P02_vscode_cli_read_only_operations(env):
    import shutil
    if not shutil.which('code'):
        pytest.skip('BLOCKED: VS Code CLI not installed.')
    version = json.loads(env.registry.execute({'action': 'vscode_cli', 'value': 'version'}, lambda: False).evidence)
    assert version['version'].count('.') == 2 and len(version['commit']) == 40
    extensions = json.loads(env.registry.execute({'action': 'vscode_cli', 'value': 'list_extensions'}, lambda: False).evidence)
    assert extensions['count'] == len(extensions['extensions'])


# ---- 5. Browser DOM automation on a controlled page (REAL headless Chrome) ---------------------------------------------
def test_P02_05_dom_fill_and_click_on_controlled_loopback_page():
    chrome = next((p for p in (Path('C:/Program Files/Google/Chrome/Application/chrome.exe'),
                               Path('C:/Program Files (x86)/Google/Chrome/Application/chrome.exe')) if p.is_file()), None)
    if chrome is None:
        pytest.skip('BLOCKED: installed Chrome not available.')
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from playwright.sync_api import sync_playwright
    from jarvis.browser_worker import Session
    page_html = (b'<label for="q">Search term</label><input id="q"><button onclick="document.getElementById(\'out\')'
                 b'.textContent=\'Saved: \'+document.getElementById(\'q\').value">Save</button><p id="out"></p>')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(page_html)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True, executable_path=str(chrome))
            try:
                context = browser.new_context()
                context.route('**/*', lambda r: r.continue_() if r.request.url.startswith(origin + '/') else r.abort())
                page = context.new_page()
                page.goto(origin + '/form')
                session = Session()
                session.page, session.context, session.open = page, context, (lambda _: None)
                report = session.inspect()
                assert any('Search term' in json.dumps(row) for row in report.get('controls', [report]))
                session.perform({'operation': 'fill', 'url': page.url, 'value': 'Search term', 'content': 'jarvis'})
                session.perform({'operation': 'click', 'url': page.url, 'value': 'Save'})
                assert page.text_content('#out') == 'Saved: jarvis'  # independent DOM readback
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_P02_05b_web_methods_rank_documented_api_before_dom(env):
    env.actions.realtime = object()
    plan = strategy.plan(env.actions, strategy.request_for('web', 'read'))
    order = [c['method'] for c in plan.candidates if c['eligible']]
    assert order[:3] == ['web.realtime_api', 'web.http_text', 'web.dom']


# ---- 6. Structured UIA on a disposable Windows app (REAL UIA) + cursor fallback -----------------------------------------
@pytest.fixture
def fixture_window():
    import win32gui
    title = 'Jarvis UIA Fixture ' + uuid.uuid4().hex[:8]
    process = subprocess.Popen([sys.executable, str(BASE / 'tests/fixtures/uia_fixture_app.py'), title])
    try:
        handle, deadline = 0, time.monotonic() + 15
        while not handle and time.monotonic() < deadline:
            handle = win32gui.FindWindow('JarvisUiaFixture', title)
            time.sleep(.05)
        if not handle:
            pytest.skip('BLOCKED: disposable Win32 window did not appear (no interactive desktop).')
        # Diagnostics only: a UIA test once stalled during a full run while the desktop was in active use.
        # If that recurs, every thread's stack is written to the log (the outcome is not changed).
        import faulthandler
        faulthandler.dump_traceback_later(180, repeat=False)
        yield handle
    finally:
        import faulthandler
        faulthandler.cancel_dump_traceback_later()
        process.kill()
        process.wait(5)


def test_P02_06_structured_uia_first_on_disposable_app(fixture_window):
    from pywinauto import Desktop
    from jarvis.execution_router import execute
    window = Desktop(backend='uia').window(handle=fixture_window).wrapper_object()
    controls = window.descendants()
    edit = next(c for c in controls if c.element_info.control_type == 'Edit')
    button = next(c for c in controls if c.element_info.control_type == 'Button' and c.window_text() == 'Apply')
    label = lambda: next(c.window_text() for c in window.descendants()
                         if c.element_info.control_type == 'Text' and c.window_text().startswith(('Applied', 'Not')))
    handle = SimpleNamespace(handle=fixture_window)
    with patch('jarvis.jarvis_pointer.tap', side_effect=AssertionError('pointer must not be used')):
        filled = execute({'operation': 'fill_text', 'content': 'structured value'}, edit,
                         {'role': 'Edit', 'name': '', 'id': list(edit.element_info.runtime_id)}, handle, lambda: None)
        clicked = execute({'operation': 'activate'}, button,
                          {'role': 'Button', 'name': 'Apply', 'id': list(button.element_info.runtime_id)}, handle,
                          lambda: None, observe=label)
    assert filled['provider'] == 'ufo' and filled['verified'] is True
    assert clicked['provider'] == 'ufo' and clicked['observed_change'] is True
    assert label() == 'Applied: structured value'


def test_P02_09_cyan_cursor_order_is_configurable_and_remains_the_fallback(tmp_path):
    from jarvis.execution_adapters import JarvisPointer, PRIORITY, desktop_order
    (tmp_path / 'config').mkdir()
    default = [p.name for p in desktop_order(tmp_path)]
    assert default[-1] == 'jarvis-pointer' and default[0] == 'ufo'
    (tmp_path / 'config/config.json').write_text(json.dumps({'execution_strategy': {'desktop_order': 'pointer_first'}}))
    assert [p.name for p in desktop_order(tmp_path)] == list(PRIORITY)
    (tmp_path / 'config/config.json').write_text('{broken')
    assert desktop_order(tmp_path)[-1] is JarvisPointer  # malformed config keeps structured first


def test_P02_09b_pointer_still_prepares_when_no_uia_pattern_exists():
    """MOCK user32/geometry (existing pointer fixture): the cyan cursor taps when patterns are absent."""
    from tests.test_desktop_control_audit import pointer_fixture
    pointer_fixture()


def test_P02_09c_router_uses_pointer_only_after_structured_providers_decline():
    """MOCK providers: structured providers decline before input; pointer then dispatches once."""
    from jarvis import execution_router
    from jarvis.execution_adapters import Prepared, Unsupported
    order = []

    def provider(name, prepared=None):
        def prepare(element, control, request, window):
            order.append(name)
            if prepared is None:
                raise Unsupported('no pattern')
            return prepared
        return type(name, (), {'name': name, 'prepare': staticmethod(prepare)})

    tapped = []
    classes = [provider(n) for n in ('ufo', 'windows-mcp', 'cua', 'open-computer-use', 'agent-s')]
    classes.append(provider('jarvis-pointer', Prepared(lambda: tapped.append(1))))
    with patch.object(execution_router, 'desktop_order', return_value=tuple(classes)):
        result = execution_router.execute({'operation': 'activate'}, object(), {'role': 'Button', 'name': 'Export'},
                                          SimpleNamespace(handle=1), lambda: None)
    assert order[-1] == 'jarvis-pointer' and order[0] == 'ufo' and tapped == [1] and result['provider'] == 'jarvis-pointer'


# ---- 8. Permissions, secrets, privacy and non-idempotent writes ---------------------------------------------------------
def test_P02_08_approval_denial_changes_nothing(env):
    path = env.folder / 'budget.xlsx'
    workbook(path)
    before = sha(path)

    def deny(kind, detail, cancelled):
        raise ValueError('Action cancelled; approval was not given.')

    env.actions._approve = deny
    with pytest.raises(ValueError, match='approval'):
        call(env, 'office_xlsx', 'budget.xlsx', operation='write', sheet='Data', cells={'A1': 99})
    assert sha(path) == before and not (env.runtime / '.jarvis-runtime/backups').exists()


def test_P02_08b_scope_policy_and_paths_are_enforced(env):
    (env.folder / 'budget.xlsx').write_bytes(b'x')
    env.actions.allowed_tools = {'strategy_execute', 'office_xlsx'}
    plan = strategy.plan(env.actions, strategy.request_for('budget.xlsx', 'write', features=('charts',)))
    excel = next(c for c in plan.candidates if c['method'] == 'xlsx.excel_com')
    assert not excel['eligible'] and 'outside the current task scope' in excel['reasons']
    env.actions.allowed_tools = None
    (env.runtime / '.jarvis').mkdir()
    (env.runtime / '.jarvis/policy.json').write_text(json.dumps({'deny_tools': ['office_automation']}))
    plan = strategy.plan(env.actions, strategy.request_for('budget.xlsx', 'write'))
    excel = next(c for c in plan.candidates if c['method'] == 'xlsx.excel_com')
    assert not excel['eligible'] and any('denied' in r for r in excel['reasons'])
    for name in ('../escape.xlsx', 'C:/Windows/win.xlsx', '.hidden.xlsx'):
        with pytest.raises(ValueError):
            call(env, 'office_xlsx', name, operation='read')


def test_P02_08c_outcome_telemetry_carries_no_document_content(env):
    path = env.folder / 'secret.xlsx'
    workbook(path)
    call(env, 'office_xlsx', 'secret.xlsx', operation='write', sheet='Data', cells={'B3': 'api_key=sk-FAKE0123456789abcdef'})
    log = (env.runtime / '.jarvis-runtime/agent-events.jsonl').read_text(encoding='utf-8')
    assert 'FAKE0123' not in log and 'secret.xlsx' not in log and 'B3' not in log
    rows = [r for r in read_outcomes(env.runtime) if r.get('adapter') == 'xlsx.openpyxl']
    assert rows[-1]['verification'] == 'verified' and rows[-1]['idempotency'] == 'non_idempotent'


def test_P02_08d_locked_or_concurrently_changed_file_is_never_overwritten(env):
    path = env.folder / 'budget.xlsx'
    workbook(path)
    original = app_adapters.commit

    def changed_meanwhile(actions, name, target, temporary, original_hash):
        target.write_bytes(target.read_bytes() + b'\0')  # simulated concurrent edit by another program
        return original(actions, name, target, temporary, original_hash)

    with patch.object(app_adapters, 'commit', changed_meanwhile):
        with pytest.raises(ValueError, match='changed while it was being edited'):
            call(env, 'office_xlsx', 'budget.xlsx', operation='write', sheet='Data', cells={'A1': 5})
    assert not list(env.folder.glob('.jarvis-*'))


# ---- Planner integration: API first, GUI last ---------------------------------------------------------------------------
def brain_for(actions):
    from jarvis.brain import Brain
    brain = Brain.__new__(Brain)
    brain.actions = actions
    actions.apps = {}
    return brain


def test_P02_planner_rejects_gui_typing_when_api_method_is_eligible(env):
    brain = brain_for(env.actions)
    step = {'action': 'type_text', 'value': 'budget.xlsx - Excel', 'content': '42'}
    with pytest.raises(ValueError, match='API/code first: use office_xlsx'):
        brain.validate_remaining([step], 'put 42 in cell B2 of budget.xlsx')
    env.actions._strategy_exhausted = {'budget.xlsx'}  # strategy reported no API/structured method can run
    brain.validate_remaining([step], 'put 42 in cell B2 of budget.xlsx')
    env.actions._strategy_exhausted = set()
    env.actions.allowed_tools = {'type_text'}  # API tools outside scope: GUI is the only authorized method
    brain.validate_remaining([step], 'put 42 in cell B2 of budget.xlsx')


def test_P02_planner_requires_named_file_and_write_intent(env):
    brain = brain_for(env.actions)
    write = {'action': 'office_xlsx', 'value': 'other.xlsx', 'folder': 'docs',
             'content': json.dumps({'operation': 'write', 'sheet': 'Data', 'cells': {'A1': 1}})}
    with pytest.raises(ValueError, match='document name you did not give'):
        brain.validate_remaining([write], 'set A1 to 1 in budget.xlsx')
    with pytest.raises(ValueError, match='no change was requested'):
        brain.validate_remaining([{**write, 'value': 'budget.xlsx'}], 'what is in budget.xlsx')
    brain.validate_remaining([{**write, 'value': 'budget.xlsx'}], 'set A1 to 1 in budget.xlsx')
    brain.validate_remaining([{**write, 'content': json.dumps({'operation': 'read'})}], 'what is in budget.xlsx')


def test_P02_capability_context_carries_strategy_order():
    from jarvis.capabilities import intents, runtime_context
    context = runtime_context('merge a.pdf and b.pdf into all.pdf',
                              [{'action': a} for a in ('strategy_execute', 'pdf_document', 'type_text')])
    assert 'documents' in intents('merge a.pdf and b.pdf into all.pdf')
    assert [row['target'] for row in context['execution_strategy']] == ['a.pdf', 'b.pdf', 'all.pdf']
    assert context['execution_strategy'][0]['order'][0] == {'method': 'pdf.pypdf', 'tool': 'pdf_document', 'tier': 'api'}


# ---- Learning from measured outcomes ------------------------------------------------------------------------------------
def outcome_rows(base, adapter, tier, verification, count):
    from jarvis.agent_events import event
    from jarvis.execution_contracts import record_outcome
    actions = SimpleNamespace(base=base)
    for _ in range(count):
        record_outcome(actions, 'office_xlsx', event(actions, 'tool.started', 'office_xlsx'), method_tier=tier,
                       adapter=adapter, verification=verification, latency_ms=100.0, attempts=1)


def test_P02_measured_failures_demote_api_but_never_enable_ineligible_methods(env):
    with patch.object(strategy, '_requirement', return_value=True):
        assert strategy.plan(env.actions, strategy.request_for('m.xlsx', 'write')).selected == 'xlsx.openpyxl'
        outcome_rows(env.runtime, 'xlsx.openpyxl', 'api', 'failed', 10)
        outcome_rows(env.runtime, 'xlsx.excel_com', 'structured', 'verified', 10)
        plan = strategy.plan(env.actions, strategy.request_for('m.xlsx', 'write'))
        api = next(c for c in plan.candidates if c['method'] == 'xlsx.openpyxl')
        assert api['demoted'] and api['measured']['failed'] == 10 and plan.selected == 'xlsx.excel_com'
        env.actions.allowed_tools = {'strategy_execute', 'office_xlsx'}
        plan = strategy.plan(env.actions, strategy.request_for('m.xlsx', 'write'))
        assert plan.selected == 'xlsx.openpyxl'  # demoted but the only authorized method; excel_com stays ineligible


def test_P02_execution_methods_tool_explains_without_running(env):
    with patch.dict(app_adapters.HANDLERS, {name: Mock(side_effect=AssertionError('must not run')) for name in app_adapters.HANDLERS}):
        result = json.loads(env.registry.execute({'action': 'execution_methods', 'value': 'scene.blend', 'folder': 'docs',
            'content': json.dumps({'operation': 'create'})}, lambda: False).evidence)
    assert result['request']['domain'] == '3d' and result['candidates'][0]['tier'] == 'api'
    assert result['transaction'] == 'new file, no-clobber publication' and result['approval_required'] is True
