"""Pint through its isolated environment. Never inject solver packages into Jarvis."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import math
import uuid
from ..contracts import Quantity

APP = Path(__file__).resolve().parents[3]


def convert(quantity: Quantity, target: str, *, journal=None) -> Quantity:
    from ..sandbox.env_manager import units_environment
    worker = Path(__file__).with_name('units_worker.py')
    python = APP / '.venv-discovery-units' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file() or not units_environment()['pins_match']:
        raise RuntimeError('isolated Pint environment is unavailable; no unit conversion performed')
    if not isinstance(target, str) or not 1 <= len(target) <= 80:
        raise ValueError('bounded target unit required')
    value = 0.0 if quantity.value is None else quantity.value
    request = json.dumps({'value': value, 'unit': quantity.unit, 'target': target}, allow_nan=False)
    budget = None
    reservation = 'units-' + uuid.uuid4().hex
    if journal is not None:
        from ..sandbox.budget import Budget
        budget = Budget(journal)
        budget.reserve(reservation, cpu_s=10.0)
    # Only this owned worker is callable. No shell, generated code or arbitrary entry point.
    try:
        done = subprocess.run([str(python), '-B', '-I', str(worker)], input=request, capture_output=True, text=True,
                              timeout=10, cwd=worker.parent,
                              env={k: v for k, v in os.environ.items() if k.upper() in
                                   {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'PATHEXT'}},
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if len(done.stdout) > 4096 or done.returncode:
            raise ValueError('unit conversion failed; incompatible dimensions or invalid unit')
        result = json.loads(done.stdout)
        if result.get('pint') != '0.25.2':
            raise RuntimeError('Pint version changed; golden qualification must be repeated')
        cpu = result.get('cpu_s')
        if type(cpu) not in (float, int) or not math.isfinite(cpu) or not 0 <= cpu <= 10:
            raise ValueError('invalid unit-worker CPU measurement')
    except BaseException:
        if budget is not None:
            budget.settle(reservation, uncertain=True)
        raise
    if budget is not None:
        budget.settle(reservation, cpu_s=cpu, disk_bytes=0)
    return Quantity(value=None if quantity.value is None else result['value'], unit=result['unit'],
                    origin=quantity.origin, source_ref=quantity.source_ref)
