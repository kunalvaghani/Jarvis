"""Typed contracts of the brain: neurons (capability nodes), synapses (guarded directed edges) and signals.

A neuron is registered, versioned code with typed input and output ports, never free LLM text. A synapse joins one
neuron's output port to another's input port when their data types match; two-way communication is two synapses,
each checked on its own. A signal is the event that travels along a synapse: it carries a reference to its data, the
causal parent, the graph version, privacy, attempt counters and an idempotency key (ARCHITECTURE.md section 4).
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, List, Literal, Optional, Tuple
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Kind = Literal['sensor', 'model', 'tool', 'mcp', 'memory', 'skill', 'workflow', 'verifier', 'route']
SideEffect = Literal['read_only', 'local_write', 'ui_or_media_state', 'external_write', 'destructive',
                     'operation_dependent', 'unknown']
Privilege = Literal['read', 'write', 'approval_required']
Privacy = Literal['public_data_only', 'local_private', 'cloud_allowed']
Status = Literal['active', 'proposed', 'disabled', 'denied']
EdgeMode = Literal['dataflow', 'feedback', 'dependency', 'conditional']
ContractSource = Literal['explicit', 'derived']

NODE_ID = re.compile(r'^[a-z][a-z0-9_]*(?:\.[a-z0-9_][a-z0-9_-]*)+@v\d+$')
# Side-effect classes that change something outside Jarvis's own memory: always behind the approval gate.
GATED_EFFECTS = frozenset({'local_write', 'external_write', 'destructive', 'operation_dependent'})
# Effects the registry cannot vouch for: never eligible until a person classifies the neuron.
UNCLASSIFIED = frozenset({'unknown'})

# Data types travelling between ports. Generic types are allowed on ports but never auto-wire a synapse: a link
# only forms on a specific type, so the graph stays sparse instead of every text tool feeding every other one.
DATA_TYPES = frozenset({
    'Goal', 'Text', 'Query', 'Url', 'SearchResults', 'WebPage', 'PageAction', 'FilePath', 'FolderPath', 'FileText',
    'FolderListing', 'AppName', 'WindowRefs', 'UiAction', 'ScreenTarget', 'CommandLine', 'CommandOutput', 'MediaQuery',
    'MediaState', 'Code', 'CodePatch', 'TestReport', 'Repository', 'BlendScene', 'Wireframe', 'Document',
    'Spreadsheet', 'Pdf', 'Image', 'Report', 'Verdict', 'MemoryHits', 'Episode', 'Plan', 'Calculation', 'Answer',
    'EmailDraft', 'Message', 'CalendarEvent', 'Issue', 'ToolList', 'Status', 'Any',
})
GENERIC_TYPES = frozenset({'Text', 'Status', 'Any', 'Answer', 'Goal'})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class Port(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,39}$')
    type: str
    required: bool = True

    @field_validator('type')
    @classmethod
    def known_type(cls, value: str) -> str:
        if value not in DATA_TYPES:
            raise ValueError(f'unknown data type {value!r}')
        return value


class Neuron(BaseModel):
    """One capability node (ARCHITECTURE.md section 4, node contract)."""
    model_config = ConfigDict(extra='forbid')
    node_id: str
    kind: Kind
    capability: str = Field(min_length=3, max_length=120)
    provider: str = Field(min_length=3, max_length=200)
    inputs: Tuple[Port, ...] = ()
    outputs: Tuple[Port, ...] = ()
    contract: ContractSource = 'derived'
    runtime: Literal['local', 'network', 'local_or_network', 'cloud'] = 'local'
    privilege: Privilege = 'read'
    privacy: Privacy = 'local_private'
    side_effect_class: SideEffect = 'unknown'
    requirements: Tuple[str, ...] = ()
    resource_cost: Dict[str, Any] = Field(default_factory=lambda: {'gpu_vram_mb': 0})
    timeout_ms: Optional[int] = Field(default=None, ge=1, le=7_200_000)
    concurrency_limit: Optional[int] = Field(default=None, ge=1, le=64)
    version: int = Field(default=1, ge=1)
    healthcheck: Optional[str] = None
    status: Status = 'active'
    tool: Optional[str] = None  # the ToolRegistry action name that executes this neuron, if any
    description: str = Field(default='', max_length=600)
    source: str = ''

    @field_validator('node_id')
    @classmethod
    def stable_id(cls, value: str) -> str:
        if not NODE_ID.match(value):
            raise ValueError(f'node id {value!r} must look like kind.name@vN')
        return value

    @model_validator(mode='after')
    def consistent(self) -> 'Neuron':
        if not self.node_id.endswith(f'@v{self.version}'):
            raise ValueError(f'{self.node_id}: id version and version field differ')
        if self.side_effect_class in GATED_EFFECTS and self.privilege == 'read':
            raise ValueError(f'{self.node_id}: a {self.side_effect_class} neuron cannot have read privilege')
        names = [p.name for p in self.inputs] + [p.name for p in self.outputs]
        if len(set(p.name for p in self.inputs)) != len(self.inputs) or \
                len(set(p.name for p in self.outputs)) != len(self.outputs):
            raise ValueError(f'{self.node_id}: duplicate port names {names}')
        if self.contract == 'explicit' and not self.outputs:
            raise ValueError(f'{self.node_id}: an explicit contract needs at least one output port')
        return self

    @property
    def gated(self) -> bool:
        return self.side_effect_class in GATED_EFFECTS or self.privilege == 'approval_required'

    def output_types(self) -> List[str]:
        return [p.type for p in self.outputs]

    def input_types(self) -> List[str]:
        return [p.type for p in self.inputs]


class Synapse(BaseModel):
    """A directed, typed, guarded edge. Two-way communication = two synapses (ARCHITECTURE.md section 1)."""
    model_config = ConfigDict(extra='forbid')
    edge_id: str
    source: str
    target: str
    out_port: str
    in_port: str
    data_type: str
    mode: EdgeMode = 'dataflow'
    on_event: str = 'neuron.succeeded'
    condition: Optional[str] = None  # a named predicate (see runtime predicates), never free code
    permission: Privilege = 'read'
    max_hops: int = Field(default=4, ge=1, le=16)
    learnable_preference: bool = True
    origin: Literal['contract', 'declared'] = 'contract'

    @model_validator(mode='after')
    def no_self_loop(self) -> 'Synapse':
        if self.source == self.target and self.mode != 'feedback':
            raise ValueError(f'{self.edge_id}: only a feedback synapse may return to its own neuron')
        if self.data_type not in DATA_TYPES:
            raise ValueError(f'{self.edge_id}: unknown data type {self.data_type!r}')
        return self


SignalType = Literal['goal.created', 'goal.understood', 'goal.verified', 'goal.failed', 'goal.cancelled',
                     'neuron.fired', 'neuron.succeeded', 'neuron.failed', 'neuron.blocked', 'approval.needed',
                     'approval.granted', 'approval.denied', 'verification.passed', 'verification.failed',
                     'route.shadow']


class Signal(BaseModel):
    """The event envelope (ARCHITECTURE.md section 4). Payloads travel by reference, never inline secrets."""
    model_config = ConfigDict(extra='forbid')
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: SignalType
    goal_id: str
    task_id: Optional[str] = None
    source_node: Optional[str] = None
    target_node: Optional[str] = None
    payload_ref: Optional[str] = None
    data_type: Optional[str] = None
    causal_parent_event_id: Optional[str] = None
    graph_version: int = 0
    privacy: Privacy = 'local_private'
    approval_scope: Optional[str] = None
    timestamp_utc: str = Field(default_factory=utc_now)
    deadline_utc: Optional[str] = None
    attempt: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=3, ge=1, le=10)
    idempotency_key: str = ''
    evidence_refs: Tuple[str, ...] = ()
    note: str = Field(default='', max_length=400)

    @model_validator(mode='after')
    def bounded(self) -> 'Signal':
        if self.attempt > self.max_attempts:
            raise ValueError('attempt exceeds max_attempts')
        if not self.idempotency_key:
            self.idempotency_key = f'{self.goal_id}:{self.task_id or "-"}:{self.target_node or self.type}:{self.attempt}'
        return self


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode('utf-8')).hexdigest()


def artifact_ref(data: Any) -> str:
    return 'artifact://sha256/' + digest(data)
