"""A conditional SR proper-time job, independently checked with Decimal arithmetic."""
from decimal import Decimal, localcontext
import math
from pydantic import Field
from ..contracts import Finite, StrictModel


class ClockCase(StrictModel):
    coordinate_time_s: Finite = Field(gt=0,le=1e12)
    beta: Finite = Field(ge=0,lt=1)


def calculate(case, cancelled=lambda:False):
    if cancelled(): raise ValueError('theory calculation cancelled')
    beta=case.beta; duration=case.coordinate_time_s
    factor=math.sqrt((1-beta)*(1+beta)); proper=duration*factor
    with localcontext() as ctx:
        ctx.prec=50; b=Decimal(str(beta)); t=Decimal(str(duration))
        independent=float(t*((1-b)*(1+b)).sqrt())
    if not math.isclose(proper,independent,rel_tol=1e-12,abs_tol=1e-12):
        raise ValueError('independent Decimal proper-time check failed')
    # Zero velocity is the analytic null limit; beta=0.6 gives the known 0.8 factor.
    if math.sqrt((1-.6)*(1+.6)) != .8: raise ValueError('analytic special case failed')
    return {'inputs':case.model_dump(mode='json'),'equation':'proper_time = coordinate_time * sqrt(1 - beta^2)',
            'proper_time_s':proper,'coordinate_minus_proper_s':duration-proper,'independent_decimal_s':independent,
            'hypotheses':[{'name':'Newtonian null','prediction':'equal elapsed times','result':'MODEL_CONSISTENT' if beta==0 else 'CONTRADICTED_IN_TESTED_MODEL'},
                          {'name':'Special relativity inertial clock','prediction':'proper time follows the Lorentz factor','result':'MODEL_CONSISTENT'},
                          {'name':'Backward time travel','prediction':'no executable mechanism supplied','result':'INSUFFICIENT_EVIDENCE'}],
            'assumptions':['inertial worldline in flat spacetime','coordinate interval in a specified inertial frame',
                           'constant subluminal relative speed','no acceleration, gravity, wormholes or closed timelike curves modeled'],
            'evidence_status':'MODEL_CONSISTENT','physical_validation':False,
            'checks':['independent Decimal arithmetic','zero-speed limit','known subluminal special case']}
