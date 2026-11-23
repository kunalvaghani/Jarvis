"""Strict scientific records; unknown numbers are null, never inferred defaults."""
from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator

Evidence = Literal['EXPERIMENTALLY_SUPPORTED', 'ESTABLISHED_THEORY', 'MODEL_CONSISTENT',
                   'SIMULATION_PASSED_WITH_ASSUMPTIONS', 'UNVERIFIED_SPECULATION',
                   'CONTRADICTED_IN_TESTED_MODEL', 'INSUFFICIENT_EVIDENCE', 'FICTIONAL_WORLD_RULES']
Reality = Literal['R1', 'R2', 'P1', 'T1', 'S1', 'F1', 'H1']
Verification = Literal['UNVERIFIED', 'LEARNED_UNVERIFIED', 'VERIFIED', 'DEGRADED', 'RETIRED']
Relation = Literal['derived_from', 'supports', 'contradicts', 'assumes', 'requires', 'affects',
                   'simulated_by', 'tested_in', 'supersedes', 'implemented_by', 'learned_in', 'uses_tool']
Identifier = Annotated[str, Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.:@/-]{0,199}$')]
Hash = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, allow_inf_nan=False)


class Quantity(StrictModel):
    value: Finite | None = None
    unit: str = Field(min_length=1, max_length=80)
    origin: Literal['unknown', 'source', 'measurement', 'solver', 'deterministic'] = 'unknown'
    source_ref: str | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def provenance_required(self):
        if self.value is None and self.origin != 'unknown':
            raise ValueError('an unknown number must keep unknown provenance')
        if self.value is not None and (self.origin == 'unknown' or not self.source_ref):
            raise ValueError('a number requires a non-LLM origin and a source reference')
        return self


class Entity(StrictModel):
    id: Identifier
    revision: int = Field(default=1, ge=1)
    evidence_status: Evidence = 'INSUFFICIENT_EVIDENCE'
    justification: str = Field(default='', max_length=2000)
    source_ids: tuple[Identifier, ...] = ()


class Source(Entity):
    kind: Literal['Source'] = 'Source'
    locator: str = Field(min_length=1, max_length=2000)
    sha256: Hash | None = None
    author: str | None = Field(default=None, max_length=200)
    license: str | None = Field(default=None, max_length=200)
    retrieved_at: str | None = Field(default=None, max_length=50)


class Claim(Entity):
    kind: Literal['Claim'] = 'Claim'
    text: str = Field(min_length=1, max_length=8000)
    reality_class: Reality
    excerpt_locator: str | None = Field(default=None, max_length=1000)
    retracted: bool = False


class Hypothesis(Entity):
    kind: Literal['Hypothesis'] = 'Hypothesis'
    statement: str = Field(min_length=1, max_length=8000)
    assumptions: tuple[str, ...] = ()
    prediction: str = Field(min_length=1, max_length=2000)
    is_null: bool = False


class Parameter(Entity):
    kind: Literal['Parameter'] = 'Parameter'
    name: str = Field(min_length=1, max_length=160)
    quantity: Quantity
    lower: Finite | None = None
    upper: Finite | None = None

    @model_validator(mode='after')
    def in_bounds(self):
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError('reversed parameter bounds')
        value = self.quantity.value
        if value is not None and ((self.lower is not None and value < self.lower) or
                                  (self.upper is not None and value > self.upper)):
            raise ValueError('parameter exceeds its approved bounds')
        return self


class Representations(StrictModel):
    native: str | None = None
    visual: str | None = None
    functional: str | None = None
    physical: str | None = None


class Component(Entity):
    kind: Literal['Component'] = 'Component'
    name: str = Field(min_length=1, max_length=200)
    reality_class: Reality
    variant: str | None = None
    parent_id: Identifier | None = None
    representations: Representations = Field(default_factory=Representations)
    mass: Quantity = Field(default_factory=lambda: Quantity(unit='kg'))
    missing: tuple[str, ...] = ()


class Scenario(Entity):
    kind: Literal['Scenario'] = 'Scenario'
    name: str = Field(min_length=1, max_length=200)
    parameters: tuple[Parameter, ...] = ()
    assumptions: tuple[str, ...] = ()
    seed: int = Field(default=0, ge=0)


class Experiment(Entity):
    kind: Literal['Experiment'] = 'Experiment'
    design_sha256: Hash
    scenario_sha256: Hash
    solver: str = Field(min_length=1, max_length=200)
    solver_version: str = Field(min_length=1, max_length=100)
    parameters: tuple[Parameter, ...] = ()
    metrics: dict[str, Quantity] = Field(default_factory=dict)
    artifact_ids: tuple[Identifier, ...] = ()
    parent_id: Identifier | None = None


class RunArtifact(Entity):
    kind: Literal['RunArtifact'] = 'RunArtifact'
    sha256: Hash
    locator: str = Field(min_length=1, max_length=2000)
    media_type: str = Field(min_length=1, max_length=100)


class Capability(Entity):
    kind: Literal['Capability'] = 'Capability'
    neuron_id: Identifier
    intents: tuple[str, ...] = Field(min_length=1)
    verification: Verification = 'UNVERIFIED'
    golden_ref: str | None = None


class Tool(Entity):
    kind: Literal['Tool'] = 'Tool'
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    environment: str = Field(min_length=1, max_length=2000)
    license: str | None = None
    verification: Verification = 'UNVERIFIED'


class Skill(Entity):
    kind: Literal['Skill'] = 'Skill'
    path: str = Field(min_length=1, max_length=2000)
    sha256: Hash
    tool_ids: tuple[Identifier, ...] = ()


class LearningEpisode(Entity):
    kind: Literal['LearningEpisode'] = 'LearningEpisode'
    gap: str = Field(min_length=1, max_length=2000)
    tool_id: Identifier
    stage: Literal['gap', 'researched', 'reviewed', 'review_failed', 'golden_failed', 'golden_passed',
                   'registered', 'promoted', 'degraded']
    successful_goal_ids: tuple[Identifier, ...] = ()
    golden_ref: str | None = None
    failure_reason: str | None = Field(default=None, max_length=2000)


Record = Annotated[Union[Source, Claim, Hypothesis, Parameter, Component, Scenario, Experiment,
                         RunArtifact, Capability, Tool, Skill, LearningEpisode], Field(discriminator='kind')]
RECORD = TypeAdapter(Record)


class Edge(StrictModel):
    source: Identifier
    source_revision: int = Field(default=1, ge=1)
    target: Identifier
    target_revision: int = Field(default=1, ge=1)
    relation: Relation
    source_ref: str = Field(min_length=1, max_length=1000)


def bounded_json(value: JsonValue, limit: int = 100_000) -> str:
    import json
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if len(text.encode('utf-8')) > limit:
        raise ValueError('scientific record exceeds its byte budget')
    return text
