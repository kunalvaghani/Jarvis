"""Versioned scientific workflow state stored only in the existing Journal."""
from enum import Enum
from typing import Literal
from pydantic import JsonValue,create_model
from pydantic import Field
from ..contracts import StrictModel


class Stage(str,Enum):
    resolve_target='resolve_target'
    requirements_and_sources='requirements_and_sources'
    discover_assets='discover_assets'
    validate_provenance='validate_provenance'
    inspect_asset='inspect_asset'
    generate_parametric_surrogate='generate_parametric_surrogate'
    assemble_physical_vehicle='assemble_physical_vehicle'
    validate_model='validate_model'
    simulate='simulate'
    independently_check='independently_check'
    compare='compare'
    present_evidence='present_evidence'
    completed='completed'


STAGES=tuple(s.value for s in Stage)


class StageResponse(StrictModel):
    stage: Stage
    facts: dict[str,JsonValue]
    files: dict[str,str]


class ScenarioAVehicleState(StrictModel):
    version: Literal[1]=1
    run_id: str=Field(pattern=r'^scenario-[a-f0-9]{32}$')
    original_goal: str=Field(min_length=1,max_length=6000)
    target_year: Literal[2025,2026]
    target_team_or_class: str=Field(min_length=1,max_length=120)
    stage: Stage=Stage.resolve_target
    stage_status: Literal['pending','running','verified','blocked','uncertain','completed']='pending'
    attempts: dict[str,int]=Field(default_factory=dict)
    state_revision: int=Field(default=0,ge=0)
    source_records: tuple[str,...]=()
    candidate_assets: tuple[str,...]=()
    selected_asset: str|None=None
    source_licenses: tuple[str,...]=()
    geometry_manifest: str|None=None
    physical_manifest: str|None=None
    solver_configuration: str|None=None
    validated_metrics: str|None=None
    evidence_files: tuple[str,...]=()
    failures: tuple[str,...]=()
    uncertainties: tuple[str,...]=()
    verified_stages: tuple[str,...]=()
    stage_artifacts: dict[str,str]=Field(default_factory=dict)


class Target(StrictModel):
    year: Literal[2025,2026]
    team_or_class: str=Field(min_length=1,max_length=120)
    goal: str=Field(min_length=1,max_length=6000)
    front_delta_deg: float=Field(ge=-10,le=10,allow_inf_nan=False)
    allow_surrogate: bool=False


# One closed action registry. Its schemas/examples are generated from these
# models rather than hand-written variants of native command arguments.
ACTION_MODELS={stage:create_model('ScenarioAction_'+stage,__base__=StrictModel,
    stage=(Literal[stage],...),target=(Target,...),previous_artifacts=(dict[str,str],...)) for stage in STAGES}


def action_arguments(stage,target,previous):
    raw={'stage':stage,'target':target.model_dump(mode='json'),'previous_artifacts':previous}
    import json
    return ACTION_MODELS[stage].model_validate_json(json.dumps(raw)).model_dump(mode='json')


def resolve(goal):
    """Narrow deterministic route; ambiguous/unrelated tasks keep normal routing."""
    import re
    if not isinstance(goal,str) or len(goal)>6000:return None
    # Native Lab commands cannot manufacture a new user goal/fallback grant.
    if re.match(r'^\s*lab\b',goal,re.I):return None
    years=set(re.findall(r'\b(?:2025|2026)\b',goal))
    if len(years)!=1 or not re.search(r'\b(?:F1|formula\s*(?:one|1))\b',goal,re.I):return None
    if not re.search(r'\b(?:dynamics|simulate|simulation|active aero)\b',goal,re.I):return None
    if re.search(r'\b(?:do not|never|without|no)\s+(?:run\s+)?(?:a\s+)?(?:simulate|simulation|dynamics)\b',goal,re.I):return None
    if not re.search(r'\b(?:find|build|model|vehicle|car)\b',goal,re.I):return None
    # The team's name comes from the user's literal target, not an asset ID.
    match=re.search(r'\b20\d{2}\s+([A-Za-z][\w-]*)\s+(?:F1|formula)',goal,re.I)
    team=match[1] if match and match[1].casefold() not in ('regulation','class') else 'F1 class'
    delta=re.search(r'\b(increase|decrease|lower|raise|change)\b[^.;]{0,85}?\s([+-]?\d+(?:\.\d+)?)\s*(?:degrees?|°)',goal,re.I)
    amount=float(delta[2]) if delta else 2.0
    number_span=delta.span(2) if delta else None
    direction=delta[1].casefold() if delta else None
    if delta is None:
        postfix=re.search(r'(?<![\w.])([+-]?\d+(?:\.\d+)?)\s*(?:degrees?|°)\s+(increase|decrease|change)\b',goal,re.I)
        if postfix:
            amount=float(postfix[1]);number_span=postfix.span(1);direction=postfix[2].casefold()
    if direction in ('decrease','lower'):amount=-abs(amount)
    # The registered recipe supports one degree-valued wing change and a
    # declared standard road test. Keep other explicit numerical/environment
    # requirements with the general brain; never silently replace them by this
    # recipe's defaults and then certify the original goal.
    remainder=re.sub(r'\b(?:2025|2026)\b','',goal)
    if number_span:
        start,end=number_span;remainder=re.sub(r'\b(?:2025|2026)\b','',goal[:start]+goal[end:])
    if re.search(r'\b\d+(?:\.\d+)?\b',remainder):return None
    if number_span is None and re.search(r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+degrees?\b',goal,re.I):return None
    if re.search(r'\b(?:radians?|mrad|gravity|temperature|humidity|rain|wet|snow|wind)\b',goal,re.I):return None
    if re.search(r'\b(?:at|on|around)\s+(?:the\s+)?[A-Z][a-zA-Z-]+',goal):return None
    # A condition such as "if no exact model exists, stop" is not permission.
    fallback=bool(re.search(r'\b(?:use|using|build|create|generate|permit|allow|accept|simulate)\b[^.;]{0,140}\bsurrogates?\b',goal,re.I))
    direct_ban=r'\b(?:no|without)\s+(?:(?:a|any|the)\s+)?surrogates?\b'
    action_ban=r"\b(?:never|do not|don['’]t)\s+(?:use|build|create|generate|simulate|accept|allow|permit)\s+(?:[\w-]+\s+){0,8}surrogates?\b"
    if re.search(direct_ban,goal,re.I) or re.search(action_ban,goal,re.I):fallback=False
    return Target(year=int(next(iter(years))),team_or_class=team,goal=goal,front_delta_deg=amount,allow_surrogate=fallback)


def target_query(target):
    identity=target.team_or_class if 'F1' in target.team_or_class else target.team_or_class+' F1'
    return f'{target.year} {identity} model'
