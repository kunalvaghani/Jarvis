"""Explicit SI primitive multibody inputs; no inferred mass or hidden geometry."""
from typing import Literal
from pydantic import Field, model_validator
from ..contracts import StrictModel, Finite


class RigidBody(StrictModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    parent: str | None = None
    position_m: tuple[Finite, Finite, Finite] = Field(description='Body/joint frame origin relative to its parent frame, or world for a root body; metres.')
    shape_center_m: tuple[Finite, Finite, Finite] = Field(description='Primitive centroid offset in this body frame; metres.')
    shape: Literal['sphere','box','capsule']
    size_m: tuple[Finite, ...] = Field(min_length=1,max_length=3,description='Sphere radius; box half extents x/y/z; capsule radius and half cylinder length. All metres.')
    mass_kg: Finite = Field(gt=0,le=1000)
    joint: Literal['fixed','free','hinge','slide']
    axis: tuple[Finite, Finite, Finite] | None = Field(default=None,description='Normalized hinge/slide axis in the body frame; omit for fixed/free.')
    initial_position: Finite | None = Field(default=None,description='Initial hinge angle in radians or slide distance in metres. Fixed/free bodies start at the declared pose with zero velocity.')
    damping: Finite = Field(ge=0,le=100)
    source_refs: tuple[str, ...] = Field(min_length=1,max_length=20)

    @model_validator(mode='after')
    def physical(self):
        import math
        expected={'sphere':1,'box':3,'capsule':2}[self.shape]
        if len(self.size_m)!=expected or any(not 0.001<=x<=10 for x in self.size_m):
            raise ValueError('positive bounded primitive dimensions required; box sizes are half extents')
        if any(abs(x)>100 for x in (*self.position_m,*self.shape_center_m)):raise ValueError('body outside bounded world')
        if self.joint in ('hinge','slide'):
            if self.axis is None or not math.isclose(sum(x*x for x in self.axis),1,abs_tol=1e-8):
                raise ValueError('hinge/slide needs an explicit normalized axis')
            if self.initial_position is None:raise ValueError('explicit initial generalized position required')
            if abs(self.initial_position)>10:raise ValueError('initial position outside bounded model')
        elif self.axis is not None or self.initial_position is not None:
            raise ValueError('fixed/free body has no scalar joint axis or initial position')
        if self.joint=='fixed' and self.damping!=0:raise ValueError('fixed bodies have no damping DOF')
        if self.joint=='free' and (self.parent is not None or self.damping!=0):raise ValueError('free joint must be rooted in world with zero damping')
        return self


class MechanicsCase(StrictModel):
    units: Literal['SI']
    bodies: tuple[RigidBody, ...] = Field(min_length=1,max_length=16)
    gravity_m_s2: tuple[Finite, Finite, Finite] = Field(description='World acceleration vector in metres per second squared.')
    duration_s: Finite = Field(gt=0,le=10)
    timestep_s: Finite = Field(ge=.0001,le=.01)
    sample_every: int = Field(ge=1,le=100,description='Record every N steps. N must divide the total step count so the final sample reaches duration_s.')
    assumptions: tuple[str, ...] = Field(min_length=1,max_length=30)

    @model_validator(mode='after')
    def topology(self):
        import math
        ids=set()
        for body in self.bodies:
            if body.id in ids or (body.parent is not None and body.parent not in ids):
                raise ValueError('unique IDs in parent-before-child acyclic order required')
            ids.add(body.id)
        steps=self.duration_s/self.timestep_s
        if not math.isclose(steps,round(steps),abs_tol=1e-7) or steps>100000:
            raise ValueError('bounded integral time-step count required')
        if round(steps)//self.sample_every>5000:raise ValueError('at most 5001 recorded samples')
        if round(steps)%self.sample_every:raise ValueError('sample interval must include the final simulation time')
        if sum(x*x for x in self.gravity_m_s2)>10000:raise ValueError('gravity exceeds model bound')
        return self


def validate_result(case, report):
    """Structural verification, not external physical validation or analytic agreement."""
    import math
    if report.get('solver')!='mujoco' or report.get('version')!='3.17.0':raise ValueError('wrong solver/version')
    rows=report['samples'];expected=round(case.duration_s/case.timestep_s)//case.sample_every+1
    if len(rows)!=expected:raise ValueError('incomplete trajectory')
    ids={b.id for b in case.bodies}
    nq=sum({'fixed':0,'free':7,'hinge':1,'slide':1}[b.joint] for b in case.bodies)
    nv=sum({'fixed':0,'free':6,'hinge':1,'slide':1}[b.joint] for b in case.bodies)
    for i,row in enumerate(rows):
        if type(row['t_s']) not in (float,int) or not math.isfinite(row['t_s']):raise ValueError('nonfinite time')
        if abs(row['t_s']-i*case.timestep_s*case.sample_every)>1e-8:raise ValueError('time grid changed')
        if set(row['positions_m'])!=ids:raise ValueError('component identities changed')
        if (len(row['qpos'])!=nq or len(row['qvel'])!=nv
                or any(len(xyz)!=3 for xyz in row['positions_m'].values())):raise ValueError('trajectory state dimensions changed')
        values=[v for xyz in row['positions_m'].values() for v in xyz]+row['qpos']+row['qvel']
        if any(type(v) not in (float,int) or not math.isfinite(v) for v in values):raise ValueError('nonfinite trajectory')
    from ..adapters.mechanics_worker import model_xml
    if report.get('mjcf')!=model_xml(case.model_dump(mode='json')):raise ValueError('editable model differs from explicit inputs')
    return {'complete_trajectory':True,'finite':True,'physical_validation':False,
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS'}
