"""Phase 2 execution-method measurements on disposable fixtures (real software only).

Each row is a real run through ToolRegistry on this machine: openpyxl/python-docx
(.venv-skills), native Excel/Word (new hidden instance), pypdf, background Blender
and a disposable Win32 UIA window. Methods whose software is missing are recorded
as BLOCKED. The GUI-coordinate path is NOT executed (it would type into the user's
live session); its step count is an authored reference plan and labelled as such.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import uuid

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
SKILLS = BASE / '.venv-skills' / 'Scripts' / 'python.exe'

GUI_REFERENCE_PLAN = [  # Authored, not executed: what a coordinate/keyboard plan needs for one cell edit.
    'open budget.xlsx', 'observe window', 'select Name Box', 'fill_text B2', 'observe selection',
    'type_text 42', 'shortcut ctrl+s', 'observe save state']


def summary(values):
    values = sorted(values)
    return {'n': len(values), 'p50_ms': round(statistics.median(values), 1), 'max_ms': round(values[-1], 1)} if values else {'n': 0}


def fixtures(folder):
    code = ("import openpyxl,docx,sys\nfrom reportlab.pdfgen import canvas\nf=sys.argv[1]\n"
            "b=openpyxl.Workbook();s=b.active;s.title='Data';s['A1']=2;s['A2']=3;s['A3']='=A1*A2';b.save(f+'/book.xlsx')\n"
            "d=docx.Document();d.add_paragraph('Status: draft');d.save(f+'/doc.docx')\n"
            "c=canvas.Canvas(f+'/a.pdf')\nfor i in range(3):\n c.drawString(72,720,'p%d'%i);c.showPage()\nc.save()")
    subprocess.run([str(SKILLS), '-c', code, str(folder)], check=True, timeout=120)


def measure(label, runs, function):
    times, errors = [], []
    for index in range(runs):
        started = time.perf_counter()
        try:
            function(index)
            times.append((time.perf_counter() - started) * 1000)
        except Exception as exc:  # Reported, never replaced by an estimate.
            errors.append(type(exc).__name__ + ': ' + str(exc)[:200])
    status = 'MEASURED' if times and not errors else ('BLOCKED' if errors and 'ToolUnavailable' in errors[0] else 'FAILED')
    return {'method': label, 'status': status, **summary(times), 'errors': errors[:3]}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    options = parser.parse_args(argv)
    out = Path(options.out)
    if out.exists():
        raise SystemExit('Refusing to overwrite preserved measurements: ' + str(out))
    from jarvis.tools import ToolRegistry
    rows = []
    with tempfile.TemporaryDirectory() as root:
        folder, runtime = Path(root) / 'docs', Path(root) / 'runtime'
        folder.mkdir()
        runtime.mkdir()
        fixtures(folder)
        actions = SimpleNamespace(base=runtime, allowed_tools=None, report=lambda *a: None, task_state=None,
                                  config=json.loads((BASE / 'config/config.json').read_text(encoding='utf-8')),
                                  _task_folder=lambda name, cancelled: str(folder),
                                  _approve=lambda *a: None)
        registry = ToolRegistry(actions)

        def run(tool, value, **content):
            return registry.execute({'action': tool, 'value': value, 'folder': 'docs', 'content': json.dumps(content)},
                                    lambda: False)

        log = runtime / '.jarvis-runtime' / 'agent-events.jsonl'
        started_calls = []

        def strategy_write(i):
            before = log.read_text(encoding='utf-8').count('"tool.started"') if log.exists() else 0
            run('strategy_execute', 'book.xlsx', operation='write', sheet='Data', cells={'B1': i})
            started_calls.append(log.read_text(encoding='utf-8').count('"tool.started"') - before)
        rows.append(measure('strategy_execute -> xlsx.openpyxl (API)', 5, strategy_write))
        rows.append(measure('xlsx.excel_com (structured, native Excel)', 3,
                            lambda i: run('office_automation', 'book.xlsx', operation='write', sheet='Data', cells={'C1': i})))
        rows.append(measure('docx.python_docx (API)', 5, lambda i: run('office_docx', 'doc.docx', operation='write',
                            edits=[{'kind': 'append_paragraph', 'text': 'row %d' % i}])))
        rows.append(measure('docx.word_com (structured, native Word)', 2, lambda i: run('office_automation', 'doc.docx',
                            operation='write', edits=[{'kind': 'append_paragraph', 'text': 'native %d' % i}])))
        rows.append(measure('pdf.pypdf compose (API)', 5, lambda i: run('pdf_document', 'a.pdf', operation='compose',
                            output='out%d.pdf' % i, sources=[{'path': 'a.pdf', 'pages': [1, 3]}])))
        rows.append(measure('blender.background create + readback (API)', 2, lambda i: run('blender_task', 's%d.blend' % i,
                            operation='create', objects=[{'type': 'cube', 'name': 'C'}])))
        rows.append(uia_row())
    result = {'schema_version': 1, 'measured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'scope': 'Real software on disposable fixtures; one machine; single sessions; includes process start.',
              'methods': rows,
              'tool_calls': {'api_path_registry_calls_per_edit': sorted(set(started_calls)),
                             'api_path_note': 'Measured tool.started rows per strategy_execute edit (outer call + nested adapter call).',
                             'gui_reference_plan_steps': len(GUI_REFERENCE_PLAN), 'gui_reference_plan': GUI_REFERENCE_PLAN,
                             'gui_note': 'Authored reference plan, NOT executed; no live GUI latency is claimed.'}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for row in rows:
        print(row['method'], row['status'], row.get('p50_ms'), row.get('errors'))


def uia_row():
    import win32gui
    from pywinauto import Desktop
    from jarvis.execution_router import execute
    title = 'Jarvis UIA Fixture ' + uuid.uuid4().hex[:8]
    process = subprocess.Popen([sys.executable, str(BASE / 'tests/fixtures/uia_fixture_app.py'), title])
    try:
        handle, deadline = 0, time.monotonic() + 15
        while not handle and time.monotonic() < deadline:
            handle = win32gui.FindWindow('JarvisUiaFixture', title)
            time.sleep(.05)
        if not handle:
            return {'method': 'windows.uia fill_text (structured)', 'status': 'BLOCKED', 'errors': ['window did not appear']}
        window = Desktop(backend='uia').window(handle=handle).wrapper_object()
        edit = next(c for c in window.descendants() if c.element_info.control_type == 'Edit')
        control = {'role': 'Edit', 'name': '', 'id': list(edit.element_info.runtime_id)}

        def fill(i):
            receipt = execute({'operation': 'fill_text', 'content': 'value %d' % i}, edit, control,
                              SimpleNamespace(handle=handle), lambda: None)
            if not receipt['verified'] or receipt['provider'] != 'ufo':
                raise ValueError('UIA receipt not verified')
        return measure('windows.uia fill_text (structured, disposable window)', 5, fill)
    finally:
        process.kill()


if __name__ == '__main__':
    main()
