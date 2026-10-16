"""API/code-first application adapters registered in the existing ToolRegistry.

Each adapter is one execution *method* (see execution_strategy.METHODS):
  office_xlsx / office_docx  openpyxl / python-docx in the separate .venv-skills
  pdf_document               pypdf in the main environment (new outputs only)
  office_automation          a new hidden Excel/Word instance (native object model)
  blender_task               fixed bpy templates in background Blender
  unreal_task                engine Build.version manifest (read-only)
  vscode_cli                 VS Code command-line interface

Writes are transactional: features the method cannot preserve are refused
before input; the edit goes to a temporary copy; an independent process reads it
back; the original is backed up; then one atomic replace commits it. Writes need
runtime approval and leave TaskState checkpoints. Nothing here retries a write.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

from .tool_errors import ToolUnavailable


def scoped_path(root, name):
    from .toolkits import scoped_path as checked  # Lazy: toolkits imports this module.
    return checked(root, name)

MAX_DOCUMENT_BYTES = 32_000_000
MAX_UNCOMPRESSED_BYTES = 200_000_000
CELL = re.compile(r'[A-Z]{1,3}[1-9][0-9]{0,6}')
NAME = re.compile(r'[A-Za-z0-9_][A-Za-z0-9 _.-]{0,62}')

# name: (toolkit, description, required environment variables, external write)
# Writes are approved per operation inside the adapter (like utility tools).
TOOLS = {
    'office_xlsx': ('office', 'Read or edit an .xlsx workbook with openpyxl (API tier). value=relative file, folder=scope, '
                    'content JSON {operation: read|inspect|write, sheet, cells:{"A1": value or "=formula"}}. Writes need '
                    'approval, refuse workbooks with macros/charts/pivots/links/drawings/signatures, back up, verify by '
                    'independent readback and commit atomically. New formulas have no cached value until Excel recalculates.', (), False),
    'office_docx': ('office', 'Read or edit a .docx document with python-docx (API tier). value=relative file, folder=scope, '
                    'content JSON {operation: read|inspect|write, edits:[{kind: append_paragraph,text,style?}|{kind: '
                    'replace_text,find,replace}|{kind: set_table_cell,table,row,column,text}]}. Refuses macros, signatures '
                    'and tracked changes; approval, backup, readback and atomic commit.', (), False),
    'pdf_document': ('pdf', 'Inspect a PDF, extract text, or compose a NEW PDF (merge/extract/rotate pages) with pypdf. '
                     'value=relative file, folder=scope, content JSON {operation: inspect|text|compose, pages?, '
                     'sources:[{path,pages?,rotate?}], output}. Never edits a PDF in place; creating output needs approval.', (), False),
    'office_automation': ('office', 'Edit .xlsx/.xlsm/.docx/.docm through a new hidden Excel or Word instance (structured '
                          'tier; Office preserves macros/charts). value=relative file, folder=scope, content JSON '
                          '{operation: write, sheet, cells} or {operation: write, edits}. Edits a temporary copy, macros '
                          'disabled, approval, backup, independent readback, atomic commit.', (), False),
    'blender_task': ('blender', 'Create primitive objects in a NEW .blend (optional glTF/OBJ/STL export) or inspect a .blend '
                     'with background Blender and fixed templates (scripts disabled). value=relative .blend, folder=scope, '
                     'content JSON {operation: create|inspect, objects:[{type,name,location?,scale?}], export?:{format,path}}.', (), False),
    'unreal_task': ('unreal', 'Read the configured Unreal Engine installation version manifest and editor command-line '
                    'availability. value=inspect. Editor Python on a project is not enabled.', (), False),
    'vscode_cli': ('vscode', 'Use the VS Code command line: value version|list_extensions|open; for open, folder=scope and '
                   'content JSON {path, line?}. Opening a file is a UI action without file changes.', (), False),
}


def settings(actions):
    config = getattr(actions, 'config', {})
    value = config.get('execution_strategy', {}) if isinstance(config, dict) else {}
    return value if isinstance(value, dict) else {}


def _root(actions, step, cancelled):
    folder = step.get('folder')
    if not isinstance(folder, str) or not folder.strip():
        raise ValueError('Name the folder that contains the file.')
    return Path(actions._task_folder(folder, cancelled)).resolve(strict=True)


def _arguments(step):
    try:
        value = json.loads(step.get('content') or '{}')
    except (ValueError, RecursionError):
        raise ValueError('Adapter content must be a JSON object.') from None
    if not isinstance(value, dict):
        raise ValueError('Adapter content must be a JSON object.')
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _checked_file(path, suffixes):
    if path.suffix.casefold() not in suffixes:
        raise ValueError('Unsupported file type for this method: ' + path.suffix)
    if not path.is_file():
        raise ValueError('The named file does not exist.')
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError('File exceeds the 32 MB document limit.')
    return path


def package_features(path):
    """Office Open XML features detected from the package listing, before any parse."""
    try:
        with zipfile.ZipFile(path) as package:
            entries = package.infolist()
            if len(entries) > 20000 or sum(e.file_size for e in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError('Document package exceeds expansion limits.')
            names = [entry.filename for entry in entries]
            features = set()
            if any(name.endswith('vbaProject.bin') for name in names):
                features.add('macros')
            if any(name.startswith('_xmlsignatures/') for name in names):
                features.add('signatures')
            if any(name.startswith('xl/charts/') for name in names):
                features.add('charts')
            if any(name.startswith(('xl/pivotTables/', 'xl/pivotCache/')) for name in names):
                features.add('pivot_tables')
            if any(name.startswith('xl/externalLinks/') for name in names):
                features.add('external_links')
            if any(name.startswith('xl/drawings/') for name in names):
                features.add('drawings')
            if 'word/document.xml' in names:
                body = package.read('word/document.xml')[:MAX_DOCUMENT_BYTES]
                if b'<w:ins ' in body or b'<w:del ' in body:
                    features.add('tracked_changes')
            return sorted(features)
    except zipfile.BadZipFile:
        raise ValueError('Not a valid Office Open XML package.') from None


def part_hash(path, suffix):
    with zipfile.ZipFile(path) as package:
        for name in package.namelist():
            if name.endswith(suffix):
                return hashlib.sha256(package.read(name)).hexdigest()
    return None


def docx_text(path):
    """Independent paragraph text from WordprocessingML (works for .docx and .docm)."""
    with zipfile.ZipFile(path) as package:
        body = package.read('word/document.xml').decode('utf-8', errors='replace')
    paragraphs = re.findall(r'<w:p[ >].*?</w:p>', body, re.S)
    return [''.join(re.findall(r'<w:t(?: [^>]*)?>([^<]*)</w:t>', p)) for p in paragraphs]


APP = Path(__file__).resolve().parents[1]  # Installation (interpreters); actions.base holds runtime state.


def interpreter(actions, kind):
    path = APP / ('.venv-skills' if kind == 'skills' else '.venv') / 'Scripts' / 'python.exe'
    if not path.is_file():
        if kind == 'main':
            return Path(sys.executable)
        raise ToolUnavailable('Separate utility environment is missing; run utility setup.')
    return path


def worker(actions, kind, request, cancelled, timeout=90):
    from .repo_acquisition import command
    python = interpreter(actions, kind)
    try:
        raw = command([str(python), '-m', 'jarvis.document_worker'], cancelled, timeout,
                      json.dumps(request).encode('utf-8'), 8_000_000)
    except ValueError as exc:
        raise ValueError('Document worker did not complete: ' + str(exc)[:300]) from None
    result = json.loads(raw.decode('utf-8'))
    if result.get('ok') is not True:
        if result.get('error_type') == 'ModuleNotFoundError':
            raise ToolUnavailable('Document library missing in ' + kind + ' environment: ' + str(result.get('error')))
        raise ValueError('Document operation refused: ' + str(result.get('error_type')) + ': ' + str(result.get('error')))
    return result['value']


def _temporary(path):
    return path.with_name('.jarvis-' + uuid.uuid4().hex[:12] + path.suffix)


def backup(actions, path):
    folder = Path(actions.base) / '.jarvis-runtime' / 'backups' / 'documents'
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    target = folder / (stamp + '-' + uuid.uuid4().hex[:8] + '-' + path.name)
    shutil.copy2(path, target)
    return target


def _state(actions):
    from .task_state import TaskState
    state = getattr(actions, 'task_state', None)
    return state if isinstance(state, TaskState) else None


def commit(actions, name, path, temporary, original_hash):
    """Back up, then atomically replace; fails closed if the file changed meanwhile."""
    if _sha256(path) != original_hash:
        raise ValueError('The file changed while it was being edited; no change committed.')
    saved = backup(actions, path)
    expected = _sha256(temporary)
    state = _state(actions)
    if state:
        state.checkpoint('action_attempted', action=name, target=path.name,
                         evidence='Verified temporary copy; atomic replace beginning. Backup ' + saved.name)
    try:
        os.replace(temporary, path)
    except PermissionError:
        raise ValueError('The file is open or locked by another program; no change committed. Close it and ask again.') from None
    if _sha256(path) != expected:
        raise ValueError('Committed file does not match the verified copy; inspect it. Backup kept: ' + str(saved))
    if state:
        state.checkpoint('observed', action=name, target=path.name, evidence='Committed bytes match the verified copy')
    return saved


def _approve(actions, name, detail, cancelled):
    actions._approve(name, json.dumps(detail, ensure_ascii=False), cancelled)


def _result(method, verification, **fields):
    return json.dumps({'method': method, 'verification': verification, **fields}, ensure_ascii=False, default=str)


# ---- XLSX (openpyxl) ------------------------------------------------------------------------------------------------
def _cells(arguments):
    cells = arguments.get('cells')
    if not isinstance(cells, dict) or not 1 <= len(cells) <= 500:
        raise ValueError('Provide 1-500 cells as {"A1": value}.')
    for coordinate, value in cells.items():
        if not isinstance(coordinate, str) or not CELL.fullmatch(coordinate):
            raise ValueError('Cells must be A1-style coordinates.')
        if not (value is None or type(value) in {bool, int, float, str}) or (isinstance(value, str) and len(value) > 8000):
            raise ValueError('Cell values must be text, numbers, booleans or empty.')
        if type(value) is float and value != value:
            raise ValueError('Cell values must be finite.')
    return cells


def _sheet(arguments, required=True):
    sheet = arguments.get('sheet')
    if sheet is None and not required:
        return None
    if not isinstance(sheet, str) or not sheet or len(sheet) > 31:
        raise ValueError('Name the worksheet.')
    return sheet


def verify_cells(before, after, sheet, cells):
    """Requested cells changed exactly; every other cell, formula and sheet is unchanged."""
    if before['sheets'] != after['sheets']:
        return False, 'Worksheet list changed.'
    for name, rows in before['cells'].items():
        current = after['cells'].get(name, {})
        for coordinate, row in rows.items():
            if name == sheet and coordinate in cells:
                continue
            old, new = row.get('formula', row.get('value')), current.get(coordinate, {})
            if old != new.get('formula', new.get('value')):
                return False, 'Unrequested cell changed: ' + name + '!' + coordinate
        extra = set(current) - set(rows) - (set(cells) if name == sheet else set())
        if extra:
            return False, 'Unrequested cells appeared.'
    written = after['cells'].get(sheet, {})
    for coordinate, value in cells.items():
        row = written.get(coordinate, {})
        actual = row.get('formula', row.get('value'))
        if value is None:
            if coordinate in written:
                return False, 'Cell ' + coordinate + ' was not cleared.'
        elif actual != value and not (type(value) in {int, float} and type(actual) in {int, float} and float(actual) == float(value)):
            return False, 'Cell ' + coordinate + ' does not hold the requested value.'
    return True, 'Requested cells read back exactly; all other cells, formulas and sheets unchanged.'


def office_xlsx(actions, step, cancelled):
    arguments = _arguments(step)
    operation = arguments.get('operation', 'read')
    path = _checked_file(scoped_path(_root(actions, step, cancelled), step['value']), {'.xlsx'})
    features = package_features(path)
    if operation == 'inspect':
        data = worker(actions, 'skills', {'operation': 'xlsx_read', 'path': str(path), 'max_cells': 20000}, cancelled)
        return _result('xlsx.openpyxl', 'verified', features=features, sheets=data['sheets'],
                       cells=sum(len(v) for v in data['cells'].values()), formula_cells=data['formula_cells'])
    if operation == 'read':
        data = worker(actions, 'skills', {'operation': 'xlsx_read', 'path': str(path), 'sheet': _sheet(arguments, False)}, cancelled)
        return _result('xlsx.openpyxl', 'verified', features=features, **data)
    if operation != 'write':
        raise ValueError('Use read, inspect or write.')
    sheet, cells = _sheet(arguments), _cells(arguments)
    unsafe = sorted(set(features) & {'macros', 'charts', 'pivot_tables', 'external_links', 'drawings', 'signatures'})
    if unsafe:
        # Refused before any input: another method (native Office) can be selected.
        raise ToolUnavailable('openpyxl cannot preserve ' + ', '.join(unsafe) + ' on save; no change made.')
    original = _sha256(path)
    before = worker(actions, 'skills', {'operation': 'xlsx_read', 'path': str(path), 'max_cells': 20000}, cancelled)
    if sheet not in before['sheets']:
        raise ValueError('Unknown worksheet.')
    _approve(actions, 'office_xlsx', {'file': path.name, 'sheet': sheet, 'cells': cells}, cancelled)
    temporary = _temporary(path)
    try:
        worker(actions, 'skills', {'operation': 'xlsx_write', 'path': str(path), 'output': str(temporary),
                                    'sheet': sheet, 'cells': cells}, cancelled)
        after = worker(actions, 'skills', {'operation': 'xlsx_read', 'path': str(temporary), 'max_cells': 20000}, cancelled)
        verified, evidence = verify_cells(before, after, sheet, cells)
        if not verified:
            raise ValueError('Verification failed before commit; original unchanged. ' + evidence)
        if cancelled():
            raise ValueError('Cancelled before commit; original unchanged.')
        saved = commit(actions, 'office_xlsx', path, temporary, original)
    finally:
        temporary.unlink(missing_ok=True)
    return _result('xlsx.openpyxl', 'verified', file=path.name, evidence=evidence, backup=saved.name,
                   note='New formulas have no cached value until Excel recalculates.')


# ---- DOCX (python-docx) ---------------------------------------------------------------------------------------------
def _edits(arguments):
    edits = arguments.get('edits')
    if not isinstance(edits, list) or not 1 <= len(edits) <= 50:
        raise ValueError('Provide 1-50 edits.')
    for edit in edits:
        if not isinstance(edit, dict) or edit.get('kind') not in {'append_paragraph', 'replace_text', 'set_table_cell'}:
            raise ValueError('Unsupported document edit.')
        texts = [edit.get(k) for k in ('text', 'find', 'replace') if k in edit]
        if any(not isinstance(t, str) or len(t) > 10000 or '\x00' in t for t in texts):
            raise ValueError('Edit text must be bounded text.')
        if edit['kind'] == 'replace_text' and (not edit.get('find') or 'replace' not in edit):
            raise ValueError('replace_text needs find and replace.')
        if edit['kind'] == 'append_paragraph' and 'text' not in edit:
            raise ValueError('append_paragraph needs text.')
        if edit['kind'] == 'set_table_cell' and (any(type(edit.get(k)) is not int or not 0 <= edit[k] <= 1000
                                                    for k in ('table', 'row', 'column')) or 'text' not in edit):
            raise ValueError('set_table_cell needs table, row, column and text.')
    return edits


def verify_document(before, after, edits):
    """Expected text effects present; paragraph count changes only by appends."""
    appended = [e['text'] for e in edits if e['kind'] == 'append_paragraph']
    if len(after) != len(before) + len(appended):
        return False, 'Paragraph count changed unexpectedly.'
    if appended and after[-len(appended):] != appended:
        return False, 'Appended paragraphs do not read back exactly.'
    body = '\n'.join(after)
    for edit in edits:
        if edit['kind'] == 'replace_text' and (edit['replace'] not in body or (edit['find'] not in edit['replace'] and edit['find'] in body)):
            return False, 'Replacement text does not read back.'
    return True, 'Requested text effects read back from the saved package; paragraph structure preserved.'


def office_docx(actions, step, cancelled):
    arguments = _arguments(step)
    operation = arguments.get('operation', 'read')
    path = _checked_file(scoped_path(_root(actions, step, cancelled), step['value']), {'.docx'})
    features = package_features(path)
    if operation in {'read', 'inspect'}:
        data = worker(actions, 'skills', {'operation': 'docx_read', 'path': str(path)}, cancelled)
        if operation == 'inspect':
            data = {'paragraphs': len(data['paragraphs']), 'tables': len(data['tables']), 'sections': data['sections']}
        return _result('docx.python_docx', 'verified', features=features, **data)
    if operation != 'write':
        raise ValueError('Use read, inspect or write.')
    edits = _edits(arguments)
    unsafe = sorted(set(features) & {'macros', 'signatures', 'tracked_changes'})
    if unsafe:
        raise ToolUnavailable('python-docx cannot safely edit a document with ' + ', '.join(unsafe) + '; no change made.')
    original, before = _sha256(path), docx_text(path)
    _approve(actions, 'office_docx', {'file': path.name, 'edits': edits}, cancelled)
    temporary = _temporary(path)
    try:
        worker(actions, 'skills', {'operation': 'docx_write', 'path': str(path), 'output': str(temporary), 'edits': edits}, cancelled)
        verified, evidence = verify_document(before, docx_text(temporary), edits)
        if verified and any(e['kind'] == 'set_table_cell' for e in edits):
            tables = worker(actions, 'skills', {'operation': 'docx_read', 'path': str(temporary)}, cancelled)['tables']
            for e in (e for e in edits if e['kind'] == 'set_table_cell'):
                if tables[e['table']][e['row']][e['column']] != e['text']:
                    verified, evidence = False, 'Table cell does not read back.'
        if not verified:
            raise ValueError('Verification failed before commit; original unchanged. ' + evidence)
        if cancelled():
            raise ValueError('Cancelled before commit; original unchanged.')
        saved = commit(actions, 'office_docx', path, temporary, original)
    finally:
        temporary.unlink(missing_ok=True)
    return _result('docx.python_docx', 'verified', file=path.name, evidence=evidence, backup=saved.name)


# ---- PDF (pypdf) ------------------------------------------------------------------------------------------------------
def _pages(value, maximum=2000):
    if value is None:
        return None
    if not isinstance(value, list) or not 1 <= len(value) <= maximum or any(type(p) is not int or not 1 <= p <= 100000 for p in value):
        raise ValueError('Pages must be a list of 1-based page numbers.')
    return value


def pdf_document(actions, step, cancelled):
    arguments = _arguments(step)
    operation = arguments.get('operation', 'inspect')
    root = _root(actions, step, cancelled)
    if operation in {'inspect', 'text'}:
        path = _checked_file(scoped_path(root, step['value']), {'.pdf'})
        request = {'operation': 'pdf_' + operation, 'path': str(path)}
        if operation == 'text':
            request['pages'] = _pages(arguments.get('pages'), 50)
        return _result('pdf.pypdf', 'verified', file=path.name, **worker(actions, 'main', request, cancelled, 60))
    if operation != 'compose':
        raise ValueError('Use inspect, text or compose.')
    sources = arguments.get('sources')
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        raise ValueError('Compose needs 1-20 sources.')
    prepared, expected = [], 0
    for source in sources:
        if not isinstance(source, dict) or set(source) - {'path', 'pages', 'rotate'}:
            raise ValueError('Each source is {path, pages?, rotate?}.')
        path = _checked_file(scoped_path(root, source.get('path', '')), {'.pdf'})
        rotate = source.get('rotate', 0)
        if rotate not in {0, 90, 180, 270}:
            raise ValueError('Rotation must be 0, 90, 180 or 270.')
        info = worker(actions, 'main', {'operation': 'pdf_inspect', 'path': str(path)}, cancelled, 60)
        if info['encrypted']:
            raise ToolUnavailable('Encrypted PDF; no output written.')
        pages = _pages(source.get('pages'))
        expected += len(pages) if pages else info['pages']
        prepared.append({'path': str(path), 'pages': pages, 'rotate': rotate})
    output = scoped_path(root, arguments.get('output', ''))
    if output.suffix.casefold() != '.pdf' or output.exists():
        raise ValueError('Name a new .pdf output; existing files are never overwritten.')
    _approve(actions, 'pdf_document', {'output': output.name, 'sources': [Path(s['path']).name for s in prepared],
                                       'pages': expected}, cancelled)
    temporary = _temporary(output)
    try:
        worker(actions, 'main', {'operation': 'pdf_compose', 'sources': prepared, 'output': str(temporary)}, cancelled, 120)
        info = worker(actions, 'main', {'operation': 'pdf_inspect', 'path': str(temporary)}, cancelled, 60)
        if info['pages'] != expected:
            raise ValueError('Composed PDF has ' + str(info['pages']) + ' pages, expected ' + str(expected) + '; nothing saved.')
        state = _state(actions)
        if state:
            state.checkpoint('action_attempted', action='pdf_document', target=output.name, evidence='Verified PDF publishing')
        os.link(temporary, output)  # Atomic no-clobber publication.
        if state:
            state.checkpoint('observed', action='pdf_document', target=output.name, evidence='New PDF published')
    finally:
        temporary.unlink(missing_ok=True)
    return _result('pdf.pypdf', 'verified', output=output.name, pages=expected,
                   evidence='Independent reread of the new PDF shows the expected page count.')


# ---- Native Office (structured tier) ---------------------------------------------------------------------------------
def _stop_owned(pid_file, started):
    """Stop only the Office instance this request created, after a bounded wait."""
    import psutil
    try:
        pid = int(Path(pid_file).read_text(encoding='ascii').strip())
        process = psutil.Process(pid)
        if process.name().upper() not in {'EXCEL.EXE', 'WINWORD.EXE'} or process.create_time() < started - 1:
            return 'not_owned'
        try:
            process.wait(timeout=10)
            return 'exited'
        except psutil.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
            return 'terminated'
    except (OSError, ValueError, psutil.Error):
        return 'unknown'


def office_automation(actions, step, cancelled):
    arguments = _arguments(step)
    if arguments.get('operation') != 'write':
        raise ValueError('Native Office automation supports write; read with office_xlsx or office_docx.')
    path = _checked_file(scoped_path(_root(actions, step, cancelled), step['value']), {'.xlsx', '.xlsm', '.docx', '.docm'})
    excel = path.suffix.casefold() in {'.xlsx', '.xlsm'}
    try:
        import win32com.client  # noqa: F401
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'Excel.Application' if excel else 'Word.Application'))
    except (ImportError, OSError):
        raise ToolUnavailable('Microsoft ' + ('Excel' if excel else 'Word') + ' automation is not installed.') from None
    features = package_features(path)
    if 'signatures' in features:
        raise ValueError('Saving would invalidate the document signature; no change made.')
    original = _sha256(path)
    macro_hash = part_hash(path, 'vbaProject.bin')
    if excel:
        sheet, cells = _sheet(arguments), _cells(arguments)
        before = worker(actions, 'skills', {'operation': 'xlsx_read', 'path': str(path), 'max_cells': 20000}, cancelled)
        if sheet not in before['sheets']:
            raise ValueError('Unknown worksheet.')
        detail = {'file': path.name, 'application': 'Excel', 'sheet': sheet, 'cells': cells}
    else:
        edits = [e for e in _edits(arguments)]
        if any(e['kind'] == 'set_table_cell' for e in edits):
            raise ValueError('Use office_docx for table cells.')
        before = docx_text(path)
        detail = {'file': path.name, 'application': 'Word', 'edits': edits}
    _approve(actions, 'office_automation', detail, cancelled)
    temporary = _temporary(path)
    shutil.copy2(path, temporary)
    pid_file = Path(tempfile.gettempdir()) / ('jarvis-office-' + uuid.uuid4().hex + '.pid')
    request = {'application': 'excel' if excel else 'word', 'path': str(temporary), 'pid_file': str(pid_file),
               **({'sheet': sheet, 'cells': cells} if excel else {'edits': edits})}
    started = time.time()
    timeout = settings(actions).get('office_timeout_seconds', 90)
    try:
        from .repo_acquisition import command
        try:
            raw = command([str(interpreter(actions, 'main')), '-m', 'jarvis.office_com_worker'], cancelled,
                          timeout if type(timeout) in {int, float} and 10 <= timeout <= 600 else 90,
                          json.dumps(request).encode('utf-8'), 1_000_000)
            reply = json.loads(raw.decode('utf-8'))
        finally:
            cleanup = _stop_owned(pid_file, started) if pid_file.exists() else 'not_started'
            pid_file.unlink(missing_ok=True)
        if reply.get('ok') is not True:
            raise ValueError('Office refused the edit on the temporary copy; original unchanged: ' + str(reply.get('error'))[:300])
        if macro_hash and part_hash(temporary, 'vbaProject.bin') != macro_hash:
            raise ValueError('Macro project changed during automation; original unchanged.')
        if excel:
            after = worker(actions, 'skills', {'operation': 'xlsx_read', 'path': str(temporary), 'max_cells': 20000}, cancelled)
            verified, evidence = verify_cells(before, after, sheet, cells)
        else:
            verified, evidence = verify_document(before, docx_text(temporary), edits)
        if not verified:
            raise ValueError('Verification failed before commit; original unchanged. ' + evidence)
        if not set(features) <= set(package_features(temporary)):
            raise ValueError('A document feature was lost during automation; original unchanged.')
        if cancelled():
            raise ValueError('Cancelled before commit; original unchanged.')
        saved = commit(actions, 'office_automation', path, temporary, original)
    finally:
        temporary.unlink(missing_ok=True)
    return _result('xlsx.excel_com' if excel else 'docx.word_com', 'verified', file=path.name, evidence=evidence,
                   backup=saved.name, preserved_features=features, office_instance=cleanup,
                   macros_preserved=bool(macro_hash))


# ---- Blender ------------------------------------------------------------------------------------------------------------
TEMPLATE = Path(__file__).resolve().parent / 'templates' / 'blender_ops.py'
PRIMITIVES = {'cube', 'sphere', 'cylinder', 'cone', 'plane', 'torus'}


def blender_executable(actions):
    configured = settings(actions).get('blender_executable')
    for candidate in (configured, shutil.which('blender')):
        if isinstance(candidate, str) and candidate and Path(candidate).is_file() and Path(candidate).name.casefold() == 'blender.exe':
            return Path(candidate)
    raise ToolUnavailable('Blender is not configured; set execution_strategy.blender_executable.')


def resource_budget(actions, cost='high'):
    """High-cost local methods wait for headroom instead of competing with the foreground."""
    import psutil
    minimum = settings(actions).get('min_available_ram_mb', 1536)
    minimum = minimum if type(minimum) is int and 256 <= minimum <= 65536 else 1536
    available = psutil.virtual_memory().available // (1024 * 1024)
    if cost == 'high' and available < minimum:
        raise ToolUnavailable(f'Only {available} MB RAM available; {minimum} MB required for this method.')
    return available


def _blender(actions, request, cancelled):
    from .repo_acquisition import command
    executable = blender_executable(actions)
    resource_budget(actions)
    with tempfile.TemporaryDirectory(prefix='jarvis-blender-') as folder:
        request_file, result_file = Path(folder) / 'request.json', Path(folder) / 'result.json'
        request_file.write_text(json.dumps(request), encoding='utf-8')
        timeout = settings(actions).get('blender_timeout_seconds', 120)
        command([str(executable), '--background', '--factory-startup', '--disable-autoexec', '--python', str(TEMPLATE),
                 '--', str(request_file), str(result_file)], cancelled,
                timeout if type(timeout) in {int, float} and 10 <= timeout <= 900 else 120, None, 4_000_000)
        if not result_file.is_file():
            raise ValueError('Blender produced no result.')
        result = json.loads(result_file.read_text(encoding='utf-8'))
    if result.get('ok') is not True:
        raise ValueError('Blender refused the operation: ' + str(result.get('error'))[:300])
    return result['value']


def blender_task(actions, step, cancelled):
    arguments = _arguments(step)
    operation = arguments.get('operation', 'inspect')
    root = _root(actions, step, cancelled)
    path = scoped_path(root, step['value'])
    if path.suffix.casefold() != '.blend':
        raise ValueError('Name a .blend file.')
    if operation == 'inspect':
        _checked_file(path, {'.blend'})
        return _result('blender.background', 'verified', file=path.name,
                       **_blender(actions, {'operation': 'inspect', 'path': str(path)}, cancelled))
    if operation != 'create':
        raise ValueError('Use create or inspect.')
    objects = arguments.get('objects')
    if not isinstance(objects, list) or not 1 <= len(objects) <= 100:
        raise ValueError('Create needs 1-100 objects.')
    names = set()
    for item in objects:
        if (not isinstance(item, dict) or set(item) - {'type', 'name', 'location', 'scale'} or item.get('type') not in PRIMITIVES
                or not isinstance(item.get('name'), str) or not NAME.fullmatch(item['name']) or item['name'] in names):
            raise ValueError('Objects need a supported type and a unique simple name.')
        names.add(item['name'])
        for key in ('location', 'scale'):
            vector = item.get(key)
            if vector is not None and (not isinstance(vector, list) or len(vector) != 3 or
                                       any(type(v) not in {int, float} or abs(v) > 1e6 or v != v for v in vector)):
                raise ValueError(key + ' must be three finite numbers.')
    if path.exists():
        raise ValueError('The .blend already exists; existing scenes are never overwritten.')
    export = arguments.get('export')
    if export is not None:
        formats = {'gltf': '.glb', 'obj': '.obj', 'stl': '.stl'}
        if not isinstance(export, dict) or export.get('format') not in formats:
            raise ValueError('Export format must be gltf, obj or stl.')
        export_path = scoped_path(root, export.get('path', ''))
        if export_path.suffix.casefold() != formats[export['format']] or export_path.exists():
            raise ValueError('Name a new export file with the matching extension.')
    _approve(actions, 'blender_task', {'file': path.name, 'objects': objects, 'export': export}, cancelled)
    staging = Path(tempfile.mkdtemp(prefix='jarvis-blender-out-'))
    try:
        temporary = staging / path.name
        request = {'operation': 'create', 'output': str(temporary), 'objects': objects}
        if export:
            request['export'] = {'format': export['format'], 'path': str(staging / export_path.name)}
        _blender(actions, request, cancelled)
        # Independent readback in a fresh Blender process with scripts disabled.
        observed = _blender(actions, {'operation': 'inspect', 'path': str(temporary)}, cancelled)
        found = {row['name']: row for row in observed['objects']}
        for item in objects:
            row = found.get(item['name'])
            if (row is None or row['type'] != 'MESH' or
                    [round(v, 4) for v in item.get('location', [0, 0, 0])] != row['location'] or
                    [round(v, 4) for v in item.get('scale', [1, 1, 1])] != row['scale']):
                raise ValueError('Readback does not match object ' + item['name'] + '; nothing saved.')
        if len(found) != len(objects):
            raise ValueError('Unexpected extra objects in the scene; nothing saved.')
        state = _state(actions)
        if state:
            state.checkpoint('action_attempted', action='blender_task', target=path.name, evidence='Verified scene publishing')
        exported = None
        for source, target in [(temporary, path)] + ([(staging / export_path.name, export_path)] if export else []):
            # Copy beside the target, then publish with an atomic no-clobber link.
            staged = _temporary(target)
            try:
                shutil.copyfile(source, staged)
                os.link(staged, target)
            finally:
                staged.unlink(missing_ok=True)
            exported = target.name if target != path else exported
        if state:
            state.checkpoint('observed', action='blender_task', target=path.name, evidence='Scene published after readback')
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return _result('blender.background', 'verified', file=path.name, export=exported,
                   objects=observed['objects'], blender_version=observed['blender_version'],
                   evidence='A second Blender process read back every requested object, transform and mesh.')


# ---- Unreal Engine ---------------------------------------------------------------------------------------------------
def unreal_task(actions, step, cancelled):
    if step['value'] != 'inspect':
        raise ValueError('Only inspect is enabled for Unreal Engine.')
    root = settings(actions).get('unreal_engine_root')
    if not isinstance(root, str) or not root:
        raise ToolUnavailable('Unreal Engine is not configured; set execution_strategy.unreal_engine_root.')
    root = Path(root)
    manifest = root / 'Engine' / 'Build' / 'Build.version'
    if not manifest.is_file() or manifest.stat().st_size > 100_000:
        raise ToolUnavailable('Unreal Engine Build.version manifest not found.')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    editor = root / 'Engine' / 'Binaries' / 'Win64' / 'UnrealEditor-Cmd.exe'
    return _result('unreal.commandlet', 'verified',
                   version='.'.join(str(data.get(k)) for k in ('MajorVersion', 'MinorVersion', 'PatchVersion')),
                   changelist=data.get('Changelist'), branch=data.get('BranchName'), editor_cmd_available=editor.is_file(),
                   editor_python='not enabled: requires a configured project and explicit approval')


# ---- VS Code -----------------------------------------------------------------------------------------------------------
def vscode_paths():
    launcher = shutil.which('code')
    if not launcher:
        raise ToolUnavailable('VS Code command line is not installed.')
    folder = Path(launcher).resolve().parent.parent
    executable, cli = folder / 'Code.exe', folder / 'resources' / 'app' / 'out' / 'cli.js'
    script = Path(launcher).with_name('code.cmd')
    if script.is_file() and script.stat().st_size < 10_000:
        # Current installs keep cli.js under a versioned folder named by the launcher script.
        match = re.search(r'%~dp0\.\.\\([A-Za-z0-9._-]{1,64})\\resources\\app\\out\\cli\.js',
                          script.read_text(encoding='utf-8', errors='replace'))
        if match:
            cli = folder / match.group(1) / 'resources' / 'app' / 'out' / 'cli.js'
    if not executable.is_file() or not cli.is_file():
        raise ToolUnavailable('VS Code executable not found next to its command line.')
    return executable, cli


def vscode(argv, cancelled, timeout=30):
    """Run Code.exe as its own CLI (what code.cmd does) without a shell."""
    from .harness_process import OwnedJob, hidden_spawn
    executable, cli = vscode_paths()
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH'}}
    env.update(ELECTRON_RUN_AS_NODE='1', VSCODE_DEV='')
    job = OwnedJob()
    try:
        with tempfile.TemporaryFile() as output:
            process = hidden_spawn(job, subprocess.Popen)([str(executable), str(cli), *argv], env=env,
                                                          stdin=subprocess.DEVNULL, stdout=output, stderr=output)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancelled() or time.monotonic() > deadline:
                    process.terminate()
                    raise ValueError('VS Code command cancelled or timed out; no retry.')
                time.sleep(.05)
            output.seek(0)
            text = output.read(200_000).decode('utf-8', errors='replace')
            if process.returncode:
                raise ValueError('VS Code command failed: ' + text[-300:])
            return text
    finally:
        job.close()


def vscode_cli(actions, step, cancelled):
    operation = step['value']
    if operation == 'version':
        lines = vscode(['--version'], cancelled).split()
        return _result('vscode.cli', 'verified', version=lines[0] if lines else '', commit=lines[1] if len(lines) > 1 else '')
    if operation == 'list_extensions':
        rows = [line for line in vscode(['--list-extensions', '--show-versions'], cancelled).splitlines() if line.strip()]
        return _result('vscode.cli', 'verified', extensions=rows[:500], count=len(rows))
    if operation != 'open':
        raise ValueError('Use version, list_extensions or open.')
    arguments = _arguments(step)
    path = scoped_path(_root(actions, step, cancelled), arguments.get('path', ''))
    if not path.is_file():
        raise ValueError('The named file does not exist.')
    line = arguments.get('line')
    if line is not None and (type(line) is not int or not 1 <= line <= 10_000_000):
        raise ValueError('Line must be a positive integer.')
    vscode(['--reuse-window', '--goto', str(path) + (':' + str(line) if line else '')], cancelled)
    return _result('vscode.cli', 'unverified', file=path.name,
                   evidence='VS Code accepted the open request; the editor window was not independently observed.')


HANDLERS = {'office_xlsx': office_xlsx, 'office_docx': office_docx, 'pdf_document': pdf_document,
            'office_automation': office_automation, 'blender_task': blender_task, 'unreal_task': unreal_task,
            'vscode_cli': vscode_cli}


def execute(actions, step, cancelled):
    if cancelled():
        raise ValueError('Cancelled before the adapter started.')
    return HANDLERS[step['action']](actions, step, cancelled)
