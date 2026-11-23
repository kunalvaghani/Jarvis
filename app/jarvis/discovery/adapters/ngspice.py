"""Fixed divider using Jarvis's existing RepositorySandbox, never a host solver.

Explicit approved proof batches have non-refundable invocation slots across
Journals and restarts. A consumed slot remains consumed after uncertain failure.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import uuid
from .divider import DividerInput, DividerVectors, netlist, verify

APP = Path(__file__).resolve().parents[3]
RUNTIME = APP / '.jarvis-runtime/discovery/tools/ngspice-linux-44.2'
IMAGE = 'sha256:fc3e504b26346d8fcfcadbb393fb7020c4f2b92c81f78c188b3711d2f40a9e0e'
LIBRARIES = {
    'libngspice0/usr/lib/x86_64-linux-gnu/libngspice.so.0.0.12':
        '8b24e526865425243ee57efa9dcbdde99e7220393eb77a1ab863e849a2e0d761',
    'libgomp1/usr/lib/x86_64-linux-gnu/libgomp.so.1.0.0':
        '6456b504ac347bd50c419667440b691f6966ad8aff5309d2f06c977fe2f9debe',
}
LIBRARY_BYTES = {list(LIBRARIES)[0]: 8858472, list(LIBRARIES)[1]: 348056}
PROOF_SCOPES = {'user-approved-linux-divider-proof-2026-11-04': 20,
                'user-approved-linux-divider-proof-extension-4-2026-11-04': 24,
                'user-approved-free-local-divider-proof-50-2026-11-04': 50}


def _proof_limit():
    approved = json.loads((RUNTIME / 'proof-authorization.json').read_text(encoding='utf-8'))
    if not isinstance(approved, dict):
        raise ValueError('invalid proof authorization record')
    limit = PROOF_SCOPES.get(approved.get('scope'))
    if limit is None or approved != {'approved': True, 'max_invocations': limit, 'image_id': IMAGE,
                                    'scope': approved['scope']}:
        raise ValueError('proof authorization differs from an explicitly reviewed batch')
    return limit


def environment():
    """Local static inspection only; importing/status never starts Docker."""
    problems = []
    for relative, expected in LIBRARIES.items():
        path = RUNTIME / relative
        if (not path.is_file() or any(p.is_symlink() for p in (path, *path.parents))
                or path.stat().st_size != LIBRARY_BYTES[relative]
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            problems.append('missing or changed reviewed library: ' + relative)
    worker = Path(__file__).with_name('ngspice_worker.py')
    staged = RUNTIME / worker.name
    if (not staged.is_file() or staged.is_symlink() or staged.stat().st_size != worker.stat().st_size
            or staged.read_bytes() != worker.read_bytes()):
        problems.append('owned solver worker not staged or changed')
    authorization = RUNTIME / 'proof-authorization.json'
    try:
        limit = _proof_limit()
    except (OSError, ValueError):
        problems.append('proof execution authorization absent')
    return {'ready': not problems, 'problems': problems, 'image_id': IMAGE, 'version': '44.2+ds-1',
            'environment': str(RUNTIME), 'library_hashes': LIBRARIES,
            'worker_sha256': hashlib.sha256(worker.read_bytes()).hexdigest(),
            'max_invocations': _proof_limit() if authorization.is_file() and not problems else None,
            'used_slots': sum((RUNTIME / f'proof-slot-{i:02}.json').exists() for i in range(50))}


def _reserve_slot(request_ref):
    for i in range(_proof_limit()):
        path = RUNTIME / f'proof-slot-{i:02}.json'
        try:
            with path.open('x', encoding='utf-8') as out:
                json.dump({'request_ref': request_ref, 'state': 'consumed-before-dispatch'}, out)
            return i
        except FileExistsError:
            continue
    raise PermissionError('approved invocation proof batch exhausted; no new execution authorized')


def solve(request: DividerInput, *, journal, cancelled=lambda: False):
    from ...repo_sandbox import RepositorySandbox
    from ..sandbox.budget import Budget
    if not isinstance(request, DividerInput):
        raise TypeError('validated divider input required')
    if cancelled():
        raise ValueError('divider cancelled before dispatch')
    state = environment()
    if not state['ready']:
        raise RuntimeError('ngspice proof unavailable: ' + '; '.join(state['problems']))
    sandbox = RepositorySandbox(IMAGE)
    status = sandbox.status(refresh=True)
    if not status['available'] or status['image_id'] != IMAGE:
        raise RuntimeError('reviewed sandbox unavailable; no host fallback')
    request_ref = journal.put({'kind': 'ngspice-divider-request', 'input': request.model_dump(mode='json'),
                               'image_id': IMAGE, 'libraries': LIBRARIES,
                               'worker_sha256': state['worker_sha256']}, data_type='Report')
    budget = Budget(journal)
    reservation = 'divider-' + uuid.uuid4().hex
    budget.reserve(reservation, cpu_s=5.0, disk_bytes=32000)
    try:
        slot = _reserve_slot(request_ref)
        output, image = sandbox.run(RUNTIME, {
            'entity': {'import_root': '.', 'module': 'ngspice_worker', 'symbol': 'solve', 'kind': 'function'},
            'arguments': request.model_dump(mode='json')}, cancelled=cancelled, timeout=15)
        if not isinstance(output, dict) or set(output) != {'vectors', 'solver', 'solver_version', 'netlist_sha256', 'cpu_s'}:
            raise ValueError('invalid solver output protocol')
        vectors = DividerVectors.model_validate_json(json.dumps(output['vectors'], allow_nan=False))
        cpu = output['cpu_s']
        if type(cpu) not in (float, int) or not math.isfinite(cpu) or not 0 <= cpu <= 5:
            raise ValueError('invalid solver CPU measurement')
        if (image != IMAGE or output['solver'] != 'ngspice-shared' or output['solver_version'] != '44.2'
                or output['netlist_sha256'] != hashlib.sha256(netlist(request).encode('ascii')).hexdigest()):
            raise ValueError('solver provenance differs from reviewed request/runtime')
        check = verify(request, vectors)
        if not check.passed:
            raise ValueError('independent divider numerical checks failed')
        result = {**output, 'input': request.model_dump(mode='json'), 'image_id': image,
                  'request_ref': request_ref, 'proof_slot': slot, 'checks': list(check.checks),
                  'evidence_status': 'SIMULATION_PASSED_WITH_ASSUMPTIONS',
                  'justification': 'Ideal linear DC resistors and ideal voltage source; no physical validation or temperature model.'}
        ref = journal.put(result, data_type='Report')
        # Only actual sandbox outputs get this receipt; synthetic numerical fixtures do not.
        with journal.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_solver_runs '
                       '(ref TEXT PRIMARY KEY, request_ref TEXT NOT NULL, worker_sha256 TEXT NOT NULL, image_id TEXT NOT NULL)')
            db.execute('INSERT INTO discovery_solver_runs VALUES (?,?,?,?)',
                       (ref, request_ref, state['worker_sha256'], image))
        from ..memory import LabMemory
        from ..contracts import Experiment, Parameter, Quantity, RunArtifact
        memory = LabMemory(journal)
        memory.migrate()
        identity = f'ngspice-divider-{slot:02}-' + ref.rsplit('/', 1)[-1][:12]
        artifact_id = identity + '-raw'
        memory.put(RunArtifact(id=artifact_id, sha256=hashlib.sha256(journal.get(ref).encode()).hexdigest(),
                               locator=ref, media_type='application/json',
                               evidence_status=result['evidence_status'], justification=result['justification']))
        memory.put(Experiment(id=identity, design_sha256=output['netlist_sha256'],
                              scenario_sha256=hashlib.sha256(b'ideal-linear-dc-no-temperature-v1').hexdigest(),
                              solver='ngspice-shared', solver_version='44.2+ds-1', artifact_ids=(artifact_id,),
                              parameters=tuple(Parameter(id=identity+'-'+name, name=name,
                                  quantity=Quantity(value=value, unit='V' if name == 'supply_v' else 'ohm',
                                                    origin='source', source_ref=request_ref))
                                  for name, value in request.model_dump().items()),
                              metrics={name: Quantity(value=value, unit='A' if name.endswith('_a') else 'V',
                                                       origin='solver', source_ref=ref)
                                       for name, value in output['vectors'].items()},
                              evidence_status=result['evidence_status'], justification=result['justification']))
        budget.settle(reservation, cpu_s=cpu, disk_bytes=len(json.dumps(result).encode()))
        return result, ref
    except BaseException:
        budget.settle(reservation, uncertain=True)
        raise
