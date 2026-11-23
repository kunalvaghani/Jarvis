"""Reviewed Lab metadata mapped to existing Neuron contracts, not a second registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal, TYPE_CHECKING
from pydantic import Field, TypeAdapter
from .contracts import StrictModel
if TYPE_CHECKING:
    from ..neural.contracts import Neuron


class Manifest(StrictModel):
    node_id: str
    kind: Literal['skill', 'verifier']
    inputs: tuple[str, ...]
    outputs: tuple[str, ...] = Field(min_length=1)
    intents: tuple[str, ...] = Field(min_length=1)
    feature: Literal['enabled', 'sim', 'research', 'learning']
    entrypoint: Literal['status', 'verify_status', 'convert_units', 'verify_units', 'simulate_divider', 'verify_divider']
    golden_test: Literal['foundation_status', 'pint_si_and_temperature', 'ngspice_dc_divider']
    model_hint: Literal['none']


def manifests() -> tuple[Manifest, ...]:
    path = Path(__file__).with_name('neurons') / 'foundations.json'
    raw = path.read_bytes()
    if path.is_symlink() or len(raw) > 32_000:
        raise ValueError('invalid owned Lab manifest')
    rows = TypeAdapter(tuple[Manifest, ...]).validate_json(raw)
    if len({r.node_id for r in rows}) != len(rows):
        raise ValueError('duplicate Lab neuron id')
    return rows


def enabled(config: Any, feature: str = 'enabled') -> bool:
    from ..flags import enabled as flag
    return flag(config, 'lab', 'enabled') and (feature == 'enabled' or flag(config, 'lab', feature))


def neurons(config: Any) -> list[Neuron]:
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    if not enabled(config):
        return []
    from .sandbox.env_manager import units_environment
    units_ready = units_environment()['pins_match']
    from .adapters.ngspice import environment
    solver_ready = environment()['ready']
    return [Neuron(node_id=m.node_id, kind=m.kind, capability=m.node_id.split('@')[0],
                   provider='jarvis.discovery.integration', contract='explicit',
                   inputs=ports(m.inputs), outputs=ports(m.outputs),
                   side_effect_class='read_only', privilege='read', runtime='local',
                   requirements=('flag:lab.enabled',) + ((f'flag:lab.{m.feature}',) if m.feature != 'enabled' else ()),
                   resource_cost={'gpu_vram_mb': 0, 'money': 0, 'cpu_s_estimate': 10}, timeout_ms=15_000,
                   status='disabled' if ((m.golden_test == 'pint_si_and_temperature' and not units_ready)
                                         or (m.golden_test == 'ngspice_dc_divider' and not solver_ready)) else 'active',
                   description=m.intents[0], source='jarvis/discovery/neurons/foundations.json')
            for m in manifests()]


def sources(config: Any) -> dict[str, Callable[[], list[Neuron]]]:
    from ..neural.registry import SOURCES
    return {**SOURCES, 'discovery': lambda: neurons(config)}


def research_config(config: Any) -> Any:
    """Only a Lab read's private configuration enables scouts. Never edit global settings."""
    if not enabled(config, 'research'):
        return config
    return {**config, 'control': {**(config.get('control') or {}), 'web_scouts': True}}
