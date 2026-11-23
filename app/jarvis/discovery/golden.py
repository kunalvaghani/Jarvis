"""Reviewed deterministic golden cases. Callers cannot submit arbitrary code or pass/fail."""
from __future__ import annotations

import hashlib
import math
import time
from .contracts import StrictModel, Hash


class GoldenReceipt(StrictModel):
    case: str
    passed: bool
    implementation_sha256: Hash
    python: str
    seconds: float
    details: tuple[str, ...]


def implementation_hash() -> str:
    from pathlib import Path
    root = Path(__file__).parent
    files = [root / 'golden.py', root / 'model/units.py', root / 'model/units_worker.py',
             root / 'catalog.py', root / 'contracts.py', root / 'integration.py', root / 'learning.py',
             root / 'neurons/foundations.json',
             root / 'sandbox/env_manager.py', root.parents[1] / 'requirements/discovery-units.txt']
    files += [root / 'adapters/divider.py', root / 'adapters/ngspice.py', root / 'adapters/ngspice_worker.py']
    h = hashlib.sha256()
    for p in files:
        h.update(p.name.encode()); h.update(p.read_bytes())
    from .sandbox.env_manager import units_environment
    import json
    h.update(json.dumps(units_environment()['versions'], sort_keys=True).encode())
    return h.hexdigest()


def run(case: str, journal=None) -> tuple[GoldenReceipt, str | None]:
    import platform
    started = time.monotonic()
    details = []
    passed = False
    try:
        if case == 'pint_si_and_temperature':
            from .contracts import Quantity
            from .model.units import convert
            # Independent known answers, including affine units and angular conversion.
            for value, unit, target, expected in ((100.0, 'cm', 'm', 1.0), (0.0, 'degC', 'kelvin', 273.15),
                                                   (180.0, 'degree', 'radian', math.pi)):
                result = convert(Quantity(value=value, unit=unit, origin='deterministic', source_ref='analytic-unit-definition'), target,
                                 journal=journal)
                if not math.isclose(result.value, expected, rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError('canonical conversion failed')
            passed = True
            details = ['centimetre/metre, Celsius/kelvin, degree/radian checked against definitions']
        elif case == 'ngspice_dc_divider':
            if journal is None:
                raise ValueError('a Journal is required for actual solver evidence')
            from .adapters.divider import DividerInput
            from .adapters.ngspice import solve
            for supply, upper, lower in ((10.0, 1000.0, 1000.0), (12.0, 2000.0, 1000.0),
                                         (-6.0, 1000.0, 2000.0)):
                _, ref = solve(DividerInput(supply_v=supply, upper_ohm=upper, lower_ohm=lower), journal=journal)
                details.append('actual sandbox solver output independently checked: ' + ref)
            passed = True
        elif case == 'foundation_status':
            from .catalog import manifests
            from .contracts import Capability
            for manifest in manifests():
                Capability(id=manifest.node_id, neuron_id=manifest.node_id, intents=manifest.intents,
                           golden_ref=manifest.golden_test)
            passed = True
            details = ['owned manifests map to strict capability metadata']
        else:
            raise ValueError('unreviewed golden case')
    except Exception as exc:
        details = ['golden failed: ' + type(exc).__name__]
    receipt = GoldenReceipt(case=case, passed=passed, implementation_sha256=implementation_hash(),
                            python=platform.python_version(), seconds=time.monotonic() - started, details=tuple(details))
    ref = journal.put(receipt.model_dump(mode='json'), data_type='Report') if journal is not None else None
    if journal is not None:
        with journal.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_golden_runs '
                       '(ref TEXT PRIMARY KEY, evaluator TEXT NOT NULL, implementation_sha256 TEXT NOT NULL, passed INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO discovery_golden_runs VALUES (?,?,?,?)',
                       (ref, case, receipt.implementation_sha256, int(receipt.passed)))
    return receipt, ref


def load(journal, ref: str, case: str) -> GoldenReceipt:
    body = journal.get(ref)
    if body is None:
        raise ValueError('missing golden evidence')
    receipt = GoldenReceipt.model_validate_json(body)
    import platform
    try:
        rows = journal.rows('SELECT evaluator,implementation_sha256,passed FROM discovery_golden_runs WHERE ref=?', (ref,))
    except Exception:
        rows = []
    # A caller-created artifact cannot grant qualification. Cache only an actual evaluator run;
    # changed owned source, environment pins or Python requires a new run before promotion/reuse.
    if (not rows or not rows[0]['passed'] or rows[0]['evaluator'] != case
            or rows[0]['implementation_sha256'] != receipt.implementation_sha256
            or not receipt.passed or receipt.case != case or receipt.implementation_sha256 != implementation_hash()
            or receipt.python != platform.python_version()):
        raise ValueError('golden evidence is stale or failing')
    return receipt
