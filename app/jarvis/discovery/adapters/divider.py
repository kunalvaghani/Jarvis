"""Reviewed DC divider contract and independent checks, without a solver fallback.

This module never loads a native library or runs a process. Numerical fixtures
can exercise verification, but cannot qualify a solver or create a golden pass.
"""
from __future__ import annotations

import hashlib
import math
from pydantic import Field
from ..contracts import Finite, Hash, StrictModel


class DividerInput(StrictModel):
    # Canonical SI only. User-facing unit conversion belongs to the Pint adapter.
    supply_v: Finite = Field(ge=-100, le=100)
    upper_ohm: Finite = Field(ge=1, le=1e9)
    lower_ohm: Finite = Field(ge=1, le=1e9)


class DividerVectors(StrictModel):
    input_v: Finite
    output_v: Finite
    supply_current_a: Finite  # SPICE sign: current into the positive voltage-source terminal.


class DividerCheck(StrictModel):
    passed: bool
    problems: tuple[str, ...]
    checks: tuple[str, ...]
    netlist_sha256: Hash
    # A model check is conditional; it cannot attest that an external solver ran.
    evidence_status: str = 'MODEL_CONSISTENT'


def netlist(request: DividerInput) -> str:
    """Only reviewed topology and numeric tokens; no supplied SPICE syntax."""
    if not isinstance(request, DividerInput):
        raise TypeError('validated divider input required')
    return ('Jarvis ideal DC divider\n'
            f'V1 vin 0 DC {request.supply_v:.17g}\n'
            f'R1 vin vout {request.upper_ohm:.17g}\n'
            f'R2 vout 0 {request.lower_ohm:.17g}\n'
            '.op\n.end\n')


def verify(request: DividerInput, vectors: DividerVectors) -> DividerCheck:
    if not isinstance(request, DividerInput) or not isinstance(vectors, DividerVectors):
        raise TypeError('validated request and solver vectors required')
    # Independent analytic oracle. These expected values are never substituted
    # for absent/failed solver outputs.
    expected_output = request.supply_v * request.lower_ohm / (request.upper_ohm + request.lower_ohm)
    expected_current = -request.supply_v / (request.upper_ohm + request.lower_ohm)
    problems = []
    if not math.isclose(vectors.input_v, request.supply_v, rel_tol=1e-8, abs_tol=1e-10):
        problems.append('voltage-source constraint failed')
    if not math.isclose(vectors.output_v, expected_output, rel_tol=1e-8, abs_tol=1e-10):
        problems.append('divider voltage differs from independent analytic solution')
    if not math.isclose(vectors.supply_current_a, expected_current, rel_tol=1e-8, abs_tol=1e-12):
        problems.append('source current or SPICE sign convention differs')
    upper_current = (vectors.input_v - vectors.output_v) / request.upper_ohm
    lower_current = vectors.output_v / request.lower_ohm
    if not math.isclose(upper_current, lower_current, rel_tol=1e-8, abs_tol=1e-12):
        problems.append('Kirchhoff current balance failed')
    return DividerCheck(passed=not problems, problems=tuple(problems),
                        checks=('voltage-source constraint', 'independent Ohm-law solution',
                                'source-current sign', 'Kirchhoff current balance'),
                        netlist_sha256=hashlib.sha256(netlist(request).encode('ascii')).hexdigest())
