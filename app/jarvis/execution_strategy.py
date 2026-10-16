"""API/code-first execution strategy over the existing ToolRegistry.

Policy: API/code first -> structured automation (DOM/UIA, native object model)
-> GUI coordinates last, but only among methods that are discovered, compatible,
available and authorized for this request. Ranking blends the tier prior with
measured verified outcomes from the shared agent event log (execution_contracts),
verification strength, latency and resource cost. Measured evidence can reorder
or demote methods; it can never make an ineligible or unauthorized method run.

The engine never dispatches by itself: every attempt is a ToolRegistry.execute
call, so scope, deny policy and runtime approval still apply. A fallback is taken
only when the previous method was provably not dispatched (ToolUnavailable is
raised before any input) or the operation is read-only. A dispatched write with an
uncertain outcome stops the plan and is never replayed on another method. GUI
methods are recommended to the planner, which must work from a fresh observation.
"""
from dataclasses import dataclass, field, asdict
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import threading
import time

from .execution_contracts import read_outcomes, record_outcome

TIER_PRIOR = {'api': 1.0, 'structured': .6, 'gui': .2}
TIER_RELIABILITY_PRIOR = {'api': .8, 'structured': .7, 'gui': .5}
VERIFICATION_STRENGTH = {'readback': 1.0, 'native_state': .8, 'observation': .4}
COST_PENALTY = {'low': 0., 'medium': .05, 'high': .1}
WRITE_OPERATIONS = frozenset({'write', 'create', 'compose', 'export', 'open'})


@dataclass(frozen=True)
class Method:
    id: str
    tool: str
    tier: str
    domain: str
    operations: frozenset
    targets: frozenset
    verification: str
    latency_ms: float
    cost: str = 'low'
    requires: tuple = ()
    unsafe_write_features: frozenset = frozenset()
    note: str = ''


def _m(identifier, tool, tier, domain, operations, targets, verification, latency, cost='low', requires=(), unsafe=(), note=''):
    return Method(identifier, tool, tier, domain, frozenset(operations), frozenset(targets), verification, latency,
                  cost, tuple(requires), frozenset(unsafe), note)


# Ordered catalogue. Every tool name must be registered in ToolRegistry; unregistered methods are never offered.
METHODS = (
    _m('xlsx.openpyxl', 'office_xlsx', 'api', 'spreadsheet', ('read', 'inspect', 'write'), ('.xlsx',), 'readback', 1500,
       requires=('skills_module:openpyxl',), unsafe=('macros', 'charts', 'pivot_tables', 'external_links', 'drawings', 'signatures'),
       note='Values and formula text round-trip; openpyxl drops VBA, charts, pivots and drawings on save.'),
    _m('xlsx.excel_com', 'office_automation', 'structured', 'spreadsheet', ('write',), ('.xlsx', '.xlsm'), 'readback', 8000,
       'high', ('com:Excel.Application', 'skills_module:openpyxl'), ('signatures',),
       'New hidden Excel instance; Excel itself saves, so macros and charts are preserved.'),
    _m('xlsx.gui', 'type_text', 'gui', 'spreadsheet', ('write',), ('.xlsx', '.xlsm', '.xls'), 'observation', 9000, 'medium',
       note='Keyboard entry into the foreground workbook from a fresh observation; last resort.'),
    _m('docx.python_docx', 'office_docx', 'api', 'document', ('read', 'inspect', 'write'), ('.docx',), 'readback', 1200,
       requires=('skills_module:docx',), unsafe=('macros', 'signatures', 'tracked_changes'),
       note='Paragraph/run text and tables; refuses edits that would break signatures or tracked changes.'),
    _m('docx.word_com', 'office_automation', 'structured', 'document', ('write',), ('.docx', '.docm'), 'readback', 9000,
       'high', ('com:Word.Application',), ('signatures',), 'New hidden Word instance; Word saves its own features.'),
    _m('docx.gui', 'type_text', 'gui', 'document', ('write',), ('.docx', '.docm', '.doc'), 'observation', 9000, 'medium'),
    _m('pdf.pypdf', 'pdf_document', 'api', 'pdf', ('read', 'inspect', 'compose'), ('.pdf',), 'readback', 800,
       requires=('main_module:pypdf',), note='Text, page count; merge/extract/rotate into a new file only.'),
    _m('blender.background', 'blender_task', 'api', '3d', ('create', 'inspect'), ('.blend',), 'readback', 5000, 'high',
       ('executable:blender',), note='Fixed bpy templates, background process, scripts disabled.'),
    _m('blender.gui', 'select', 'gui', '3d', ('create',), ('.blend',), 'observation', 15000, 'medium',
       note='Interactive Blender UI from fresh observation; last resort.'),
    _m('unreal.manifest', 'unreal_task', 'api', '3d', ('inspect',), ('unreal',), 'readback', 50,
       requires=('executable:unreal',), note='Engine Build.version manifest; editor Python not enabled.'),
    _m('web.realtime_api', 'realtime_query', 'api', 'web', ('read',), ('web',), 'readback', 900, requires=('realtime',),
       note='Documented public JSON APIs registered in realtime_sources only.'),
    _m('web.http_text', 'scrape_web', 'api', 'web', ('read',), ('web',), 'observation', 1500,
       note='Public page text over HTTP; no JavaScript, no authentication, no undocumented endpoints.'),
    _m('web.dom', 'browser_inspect', 'structured', 'web', ('read', 'inspect'), ('web',), 'native_state', 3000, 'medium'),
    _m('web.dom_fill', 'browser_fill', 'structured', 'web', ('write',), ('web',), 'native_state', 3000, 'medium'),
    _m('vscode.cli', 'vscode_cli', 'api', 'editor', ('inspect', 'open'), ('vscode',), 'readback', 1500,
       requires=('executable:code',)),
    _m('vscode.uia', 'select', 'structured', 'editor', ('open',), ('vscode',), 'native_state', 2500),
    _m('windows.open', 'open', 'api', 'desktop', ('open',), ('app',), 'observation', 1200),
    _m('windows.uia', 'select', 'structured', 'desktop', ('write', 'open'), ('app',), 'native_state', 1500),
    _m('windows.visual', 'save_file', 'gui', 'desktop', ('write',), ('app',), 'observation', 8000, 'medium',
       note='Visual fallback with the cyan cursor for controls without accessibility data.'),
)
BY_ID = {method.id: method for method in METHODS}
SUFFIX_DOMAIN = {'.xlsx': 'spreadsheet', '.xlsm': 'spreadsheet', '.xls': 'spreadsheet', '.docx': 'document',
                 '.docm': 'document', '.doc': 'document', '.pdf': 'pdf', '.blend': '3d'}
KEYWORD_TARGET = {'unreal': ('3d', 'unreal'), 'vscode': ('editor', 'vscode'), 'web': ('web', 'web'), 'app': ('desktop', 'app')}
# Unquoted names cannot contain spaces (else "set B2 in budget.xlsx" is one name); quoted names may.
FILE_IN_GOAL = re.compile(r'["“\']([^"”\'\\/:*?<>|]{1,120}\.(?:xlsx|xlsm|xls|docx|docm|doc|pdf|blend))["”\']'
                          r'|(?<![\w.-])([\w()-][\w().-]{0,120}\.(?:xlsx|xlsm|xls|docx|docm|doc|pdf|blend))\b', re.I)


def files_in(goal):
    return list(dict.fromkeys(quoted or bare for quoted, bare in FILE_IN_GOAL.findall(str(goal))))
GUI_TOOLS = frozenset({'type_text', 'select', 'fill_text', 'save_file', 'shortcut', 'open_menu', 'handle_dialog'})
ADAPTER_TOOLS = frozenset({'office_xlsx', 'office_docx', 'pdf_document', 'office_automation', 'blender_task',
                           'unreal_task', 'vscode_cli'})


@dataclass(frozen=True)
class Request:
    domain: str
    operation: str
    target: str
    suffix: str = ''
    features: tuple = ()


@dataclass
class Candidate:
    method: str
    tool: str
    tier: str
    eligible: bool
    reasons: list
    score: float = 0.
    demoted: bool = False
    measured: dict = field(default_factory=dict)
    approval_required: bool = False


@dataclass
class ExecutionPlan:
    request: dict
    candidates: list
    selected: str
    fallbacks: list
    gui_fallback: str
    preconditions: list
    postconditions: list
    idempotency: str
    max_attempts: int
    approval_required: bool
    privacy: str
    resource_cost: str
    transaction: str
    telemetry: str = 'tool.outcome rows in .jarvis-runtime/agent-events.jsonl (adapter = method id)'

    def to_dict(self):
        return asdict(self)


def request_for(target, operation, domain=None, features=()):
    if not isinstance(operation, str) or operation not in {'read', 'inspect', 'write', 'create', 'compose', 'export', 'open'}:
        raise ValueError('Unsupported operation for execution strategy.')
    text = str(target or '')
    suffix = Path(text).suffix.casefold()
    if suffix in SUFFIX_DOMAIN:
        inferred, kind = SUFFIX_DOMAIN[suffix], suffix
    elif text.casefold() in KEYWORD_TARGET:
        inferred, kind = KEYWORD_TARGET[text.casefold()]
    elif re.match(r'https?://', text, re.I):
        inferred, kind = 'web', 'web'
    else:
        inferred, kind = 'desktop', 'app'
    if domain is not None and domain != inferred:
        raise ValueError('Requested domain does not match the target.')
    return Request(inferred, operation, text, kind, tuple(sorted(features)))


def discover(request):
    return [m for m in METHODS if m.domain == request.domain and request.operation in m.operations
            and request.suffix in m.targets]


_AVAILABILITY = {}
_AVAILABILITY_LOCK = threading.Lock()


def _requirement(actions, requirement):
    key = (str(getattr(actions, 'base', '')), requirement)
    with _AVAILABILITY_LOCK:
        cached = _AVAILABILITY.get(key)
        if cached and time.monotonic() - cached[1] < 60:
            return cached[0]
    kind, _, name = requirement.partition(':')
    try:
        if kind == 'skills_module':
            from .app_adapters import APP
            ok = (APP / '.venv-skills' / 'Lib' / 'site-packages' / name).is_dir()
        elif kind == 'main_module':
            ok = importlib.util.find_spec(name) is not None
        elif kind == 'com':
            import winreg
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, name))
            ok = True
        elif requirement == 'executable:blender':
            from .app_adapters import blender_executable
            blender_executable(actions)
            ok = True
        elif requirement == 'executable:unreal':
            from .app_adapters import settings
            root = settings(actions).get('unreal_engine_root')
            ok = isinstance(root, str) and (Path(root) / 'Engine' / 'Build' / 'Build.version').is_file()
        elif requirement == 'executable:code':
            ok = shutil.which('code') is not None
        elif requirement == 'realtime':
            ok = getattr(actions, 'realtime', None) is not None
        else:
            ok = False
    except Exception:  # Any probe failure means unavailable (fail closed), never a crash in planning.
        ok = False
    with _AVAILABILITY_LOCK:
        _AVAILABILITY[key] = (ok, time.monotonic())
    return ok


def eligibility(actions, method, request):
    """Registered, in scope, not denied, available and able to preserve the file."""
    from .tools import TOOL_NAMES
    from .agent_events import check_policy
    reasons = []
    if method.tool not in TOOL_NAMES:
        reasons.append('tool not registered')
    allowed = getattr(actions, 'allowed_tools', None)
    if isinstance(allowed, (set, frozenset)) and method.tool not in allowed:
        reasons.append('outside the current task scope')
    try:
        check_policy(actions, method.tool)
    except ValueError as exc:
        reasons.append(str(exc)[:120])
    for requirement in method.requires:
        if not _requirement(actions, requirement):
            reasons.append('unavailable: ' + requirement)
    if request.operation in WRITE_OPERATIONS:
        lost = sorted(set(request.features) & method.unsafe_write_features)
        if lost:
            reasons.append('cannot preserve ' + ', '.join(lost))
    return not reasons, reasons


_STATS = {}
_STATS_LOCK = threading.Lock()


def measured(base):
    """Verified-outcome statistics per method from the shared event log (cached by file stamp)."""
    path = Path(base) / '.jarvis-runtime' / 'agent-events.jsonl'
    try:
        stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    except OSError:
        return {}
    with _STATS_LOCK:
        cached = _STATS.get(str(path))
        if cached and cached[0] == stamp:
            return cached[1]
    rows = {}
    for row in read_outcomes(base, 5000):
        adapter = row.get('adapter')
        if adapter not in BY_ID:
            continue
        item = rows.setdefault(adapter, {'verified': 0, 'failed': 0, 'unverified': 0, 'observed_change': 0, 'latency': []})
        state = row.get('verification')
        if state in item:
            item[state] += 1
        if isinstance(row.get('latency_ms'), (int, float)):
            item['latency'].append(row['latency_ms'])
    for item in rows.values():
        item['latency_ms_p50'] = statistics.median(item['latency']) if item['latency'] else None
        del item['latency']
    with _STATS_LOCK:
        _STATS[str(path)] = (stamp, rows)
    return rows


def score(method, stats):
    """Explainable score; returns (score, demoted, details)."""
    verified, failed = stats.get('verified', 0), stats.get('failed', 0)
    partial = stats.get('unverified', 0) + stats.get('observed_change', 0)
    samples = verified + failed + partial
    reliability = (verified + 1) / (verified + failed + .5 * partial + 2)
    confidence = samples / (samples + 5)
    effective = confidence * reliability + (1 - confidence) * TIER_RELIABILITY_PRIOR[method.tier]
    latency = stats.get('latency_ms_p50') if samples >= 3 and stats.get('latency_ms_p50') is not None else method.latency_ms
    latency_penalty = min(.15, math.log10(1 + latency / 100) * .05)
    value = (.4 * TIER_PRIOR[method.tier] + .45 * effective + .15 * VERIFICATION_STRENGTH[method.verification]
             - latency_penalty - COST_PENALTY[method.cost])
    # Repeated measured failure demotes a method below every healthy one, whatever its tier.
    demoted = samples >= 5 and effective < .4
    return round(value, 4), demoted, {'samples': samples, 'verified': verified, 'failed': failed,
                                      'unverified': partial, 'effective_reliability': round(effective, 4),
                                      'latency_ms': latency, 'latency_source': 'measured' if samples >= 3 else 'prior'}


def plan(actions, request):
    stats = measured(actions.base) if getattr(actions, 'base', None) else {}
    candidates = []
    for method in discover(request):
        ok, reasons = eligibility(actions, method, request)
        value, demoted, details = score(method, stats.get(method.id, {}))
        candidates.append(Candidate(method.id, method.tool, method.tier, ok, reasons, value, demoted, details,
                                    request.operation in WRITE_OPERATIONS))
    candidates.sort(key=lambda c: (not c.eligible, c.demoted, c.tier == 'gui', -c.score))
    runnable = [c for c in candidates if c.eligible and c.tier != 'gui']
    gui = next((c.method for c in candidates if c.eligible and c.tier == 'gui'), '')
    write = request.operation in WRITE_OPERATIONS
    return ExecutionPlan(
        request=asdict(request), candidates=[asdict(c) for c in candidates],
        selected=runnable[0].method if runnable else '', fallbacks=[c.method for c in runnable[1:]], gui_fallback=gui,
        preconditions=['target resolved inside the named folder', 'method available and in scope',
                       'document features preserved by the method'] + (['runtime approval'] if write else []),
        postconditions=(['independent readback matches the request', 'unrequested content unchanged']
                        if write else ['result parsed from the method output']),
        idempotency='read_only' if not write else 'non_idempotent', max_attempts=1 if write else 2,
        approval_required=write, privacy='local_only' if request.domain != 'web' else 'public_web_only',
        resource_cost=BY_ID[runnable[0].method].cost if runnable else 'none',
        transaction=('temporary copy, backup, atomic replace' if request.operation == 'write'
                     else 'new file, no-clobber publication' if write else 'read-only'))


def method_for(tool, step):
    """Which catalogue method a dispatched tool call represents (for telemetry)."""
    if tool not in {m.tool for m in METHODS}:
        return None
    suffix = Path(str(step.get('value', ''))).suffix.casefold()
    if tool == 'office_automation':
        return 'xlsx.excel_com' if suffix in {'.xlsx', '.xlsm'} else 'docx.word_com'
    if tool == 'type_text':
        title = str(step.get('value', '')).casefold()
        return 'xlsx.gui' if 'excel' in title or '.xls' in title else 'docx.gui' if 'word' in title or '.doc' in title else None
    if tool == 'select':
        return None  # Shared by several domains; attribution would be a guess.
    matches = [m for m in METHODS if m.tool == tool]
    return matches[0].id if len(matches) == 1 else None


def observe(actions, tool, step, call_id, latency_ms, result=None, category=None):
    """Record one outcome row after a dispatched call; never alters the tool result."""
    if not getattr(actions, 'base', None) or not isinstance(step, dict):
        return
    identifier = method_for(tool, step)
    if identifier is None or category in {'invalid_arguments', 'unavailable', 'cancelled'}:
        return  # Not dispatched: nothing to learn about the method's reliability.
    method = BY_ID[identifier]
    read_only = _operation(step) in {'read', 'inspect', 'text', 'version', 'list_extensions'} or method.tool in {
        'realtime_query', 'scrape_web', 'browser_inspect', 'unreal_task'}
    if category is None:
        state = 'unverified'
        evidence = getattr(result, 'evidence', '')
        try:
            data = json.loads(evidence) if isinstance(evidence, str) and evidence.startswith('{') else None
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get('verification') in {'verified', 'observed_change', 'unverified'}:
            state = data['verification']
        elif read_only:
            state = 'verified'
    else:
        state = 'failed' if read_only else 'unverified'
    try:
        record_outcome(actions, tool, call_id, method_tier=method.tier, adapter=method.id,
                       idempotency='read_only' if read_only else 'non_idempotent', verification=state,
                       latency_ms=latency_ms, attempts=1)
    except (OSError, ValueError):
        pass  # Telemetry cannot change an action outcome.


def _operation(step):
    try:
        content = json.loads(step.get('content') or '{}')
    except (ValueError, RecursionError):
        return ''
    if isinstance(content, dict) and isinstance(content.get('operation'), str):
        return content['operation']
    return str(step.get('value', ''))


def _request_from_step(actions, step, cancelled):
    try:
        content = json.loads(step.get('content') or '{}')
    except (ValueError, RecursionError):
        raise ValueError('Strategy content must be a JSON object.') from None
    if not isinstance(content, dict) or not isinstance(content.get('operation'), str):
        raise ValueError('Strategy content needs an operation.')
    target = step['value']
    features = ()
    suffix = Path(target).suffix.casefold()
    if suffix in {'.xlsx', '.xlsm', '.docx', '.docm'} and step.get('folder'):
        from .app_adapters import _root, package_features
        from .toolkits import scoped_path
        path = scoped_path(_root(actions, step, cancelled), target)
        if path.is_file():
            features = tuple(package_features(path))
    return request_for(target, content['operation'], content.get('domain'), features), content


def strategy_tool(actions, step, cancelled):
    from .toolkits import ToolUnavailable
    request, content = _request_from_step(actions, step, cancelled)
    chosen = plan(actions, request)
    if step['action'] == 'execution_methods':
        return json.dumps(chosen.to_dict(), ensure_ascii=False)
    from .tools import ToolRegistry
    registry = ToolRegistry(actions)
    arguments = {k: v for k, v in content.items() if k != 'domain'}
    attempts = []
    for identifier in [chosen.selected] + chosen.fallbacks if chosen.selected else []:
        method = BY_ID[identifier]
        call = {'action': method.tool, 'value': step['value'], 'folder': step.get('folder', ''),
                'content': json.dumps(arguments, ensure_ascii=False)}
        for attempt in range(chosen.max_attempts):
            try:
                result = registry.execute(call, cancelled)
                attempts.append({'method': identifier, 'status': 'completed'})
                return json.dumps({'method': identifier, 'tier': method.tier, 'attempts': attempts,
                                   'result': json.loads(result.evidence) if result.evidence.startswith('{') else result.evidence},
                                  ensure_ascii=False, default=str)
            except ToolUnavailable as exc:
                # Refused before any input: the next eligible method may run.
                attempts.append({'method': identifier, 'status': 'not_dispatched', 'reason': str(exc)[:200]})
                break
            except (OSError, TimeoutError) as exc:
                if chosen.idempotency == 'read_only' and attempt + 1 < chosen.max_attempts and not cancelled():
                    attempts.append({'method': identifier, 'status': 'retry_read', 'reason': type(exc).__name__})
                    continue
                raise
            # Any other failure may follow an external effect: stop, never replay elsewhere.
    exhausted = getattr(actions, '_strategy_exhausted', None)
    if not isinstance(exhausted, set):
        exhausted = set()
        try:
            actions._strategy_exhausted = exhausted  # Session-scoped: unlocks GUI fallback for this target only.
        except AttributeError:
            pass
    exhausted.add(Path(step['value']).name.casefold())
    raise ToolUnavailable('No API or structured method could run this ' + request.operation + '; nothing was changed. ' +
                          ('GUI fallback from a fresh observation: ' + chosen.gui_fallback + '. ' if chosen.gui_fallback else '') +
                          '; '.join(a['method'] + ': ' + a.get('reason', a['status']) for a in attempts))


def api_alternative(actions, goal, step):
    """For a GUI step on a named document, the higher-tier tool that should be used instead."""
    if step.get('action') not in GUI_TOOLS:
        return None
    exhausted = getattr(actions, '_strategy_exhausted', None)
    exhausted = exhausted if isinstance(exhausted, set) else set()
    text = (str(step.get('value', '')) + ' ' + str(step.get('content', ''))).casefold()
    for name in files_in(goal):
        file_name = Path(name).name
        stem = Path(file_name).stem.casefold()
        application = {'spreadsheet': 'excel', 'document': 'word', '3d': 'blender', 'pdf': 'pdf'}.get(
            SUFFIX_DOMAIN.get(Path(file_name).suffix.casefold()), '')
        if file_name.casefold() in exhausted or not (stem in text or (application and application in text)):
            continue
        try:
            request = request_for(file_name, 'write' if step['action'] != 'select' else 'create')
        except ValueError:
            continue
        for method in discover(request):
            if method.tier != 'gui' and eligibility(actions, method, request)[0]:
                return method.tool, file_name
    return None


def hint(goal, offered):
    """Planner context: preferred method order for documents/apps named in the request."""
    rows = []
    for name in files_in(goal)[:3]:
        file_name = Path(name).name
        domain = SUFFIX_DOMAIN.get(Path(file_name).suffix.casefold())
        methods = [m for m in METHODS if m.domain == domain and Path(file_name).suffix.casefold() in m.targets]
        rows.append({'target': file_name,
                     'order': [{'method': m.id, 'tool': m.tool, 'tier': m.tier} for m in methods if m.tool in offered],
                     'use': 'strategy_execute picks the best eligible method with measured reliability; '
                            'GUI tools only after it reports that no API or structured method can run.'})
    for word, target in (('blender', '.blend'), ('unreal', 'unreal'), ('vs code', 'vscode'), ('vscode', 'vscode')):
        if word in str(goal).casefold() and not any(r['target'].endswith(target) for r in rows):
            rows.append({'target': word, 'order': [{'method': m.id, 'tool': m.tool, 'tier': m.tier}
                                                   for m in METHODS if target in m.targets and m.tool in offered]})
    return rows


TOOLS = {
    'execution_methods': ('execution', 'Rank execution methods for an operation on a target without running anything '
                          '(API/code first, structured automation next, GUI coordinates last), with eligibility reasons '
                          'and measured reliability. value=target file/app (web, vscode, unreal), folder=scope for files, '
                          'content JSON {operation: read|inspect|write|create|compose|open}.', (), False),
    'strategy_execute': ('execution', 'Run a document/3D/editor operation through the best eligible API or structured '
                         'method, with safe fallback only before any input. value=target file, folder=scope, content '
                         'JSON {operation, ...method arguments (sheet, cells, edits, objects, sources, output)}. Writes '
                         'need approval and are never replayed; GUI fallback is reported, not executed.', (), False),
}
