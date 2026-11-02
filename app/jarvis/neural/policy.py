"""Hard eligibility: may this neuron run for this goal at all? Never learnable (ARCHITECTURE.md section 5).

eligible = active AND classified AND allowed for this session AND requirements present AND privacy allows AND
           the request itself is not off limits. Neurons that change the world stay eligible but are marked
           ``needs_approval``: the existing approval gate (``control/policy.ApprovalGate``, ``Actions._approve``)
           decides at execution time, and nothing learned can skip it.
Secrets are checked by *name* only (is the variable set?); values are never read into the brain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import os
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .contracts import Neuron

SECRET_HINT = re.compile(r'\b(?:api[ _-]?keys?|secrets?|passwords?|passwd|tokens?|credentials?|private keys?|\.env)\b|'
                         r'\bsk-[A-Za-z0-9_-]{8,}', re.I)
NETWORK = frozenset({'network', 'cloud', 'local_or_network'})
# Sending something secret-looking off this PC: refused for the whole goal, whatever the route.
EXFILTRATE = re.compile(r'\b(?:post|upload|send|share|paste|publish|email|e-mail|tweet|submit|sync|copy)\b'
                        r'(?:[^.]|\.(?=\S))*\b(?:to|on|onto|into|via|with)\b(?:[^.]|\.(?=\S))*'
                        r'(?:\b[a-z0-9-]+\.(?:com|net|org|io|dev|app|bin)\b|https?://|'
                        r'\b(?:pastebin|gist|slack|discord|twitter|server|cloud|website|internet|someone)\b)', re.I)


def goal_refusal(goal: str) -> Optional[str]:
    """Why the whole goal is off limits, or None. Checked before any neuron is ranked."""
    from ..request_safety import refusal
    refused = refusal(goal)
    if refused:
        return str(refused)
    if SECRET_HINT.search(goal or '') and EXFILTRATE.search(goal or ''):
        return ("I won't do that: the request would send something that looks secret (a key, password or token) "
                'off this PC. Secrets never leave Jarvis.')
    return None


@dataclass
class Context:
    goal: str = ''
    config: Any = None
    allowed_tools: Optional[Iterable[str]] = None
    environ: Optional[Mapping[str, str]] = None
    base: Any = None
    privacy: str = 'local_private'
    contains_secret: bool = False

    def __post_init__(self) -> None:
        self.contains_secret = self.contains_secret or bool(SECRET_HINT.search(self.goal or ''))


@dataclass
class Eligibility:
    node_id: str
    eligible: bool
    needs_approval: bool = False
    reasons: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {'node': self.node_id, 'eligible': self.eligible, 'needs_approval': self.needs_approval,
                'reasons': self.reasons}


def _requirement(req: str, ctx: Context) -> Optional[str]:
    """None when met, else the reason it is not."""
    kind, _, name = req.partition(':')
    environ = ctx.environ if ctx.environ is not None else os.environ
    if kind == 'secret':
        return None if environ.get(name) else f'{name} is not configured'
    if kind == 'flag':
        from .. import flags
        group, _, key = name.partition('.')
        try:
            return None if flags.enabled(ctx.config or {}, group, key) else f'flag {name} is off'
        except KeyError:
            return f'unknown flag {name}'
    if kind == 'mcp_server':
        from .registry import mcp_config
        spec = mcp_config(ctx.base) if ctx.base is not None else mcp_config()
        return None if (spec.get(name) or {}).get('enabled') else f'MCP server {name} is not enabled'
    if kind == 'control_backend':  # e.g. control_backend:pc=agent_desktop: the neuron's backend is switched on
        from ..control.backends import pc_backend, web_backend
        which, _, wanted = name.partition('=')
        current = (pc_backend if which == 'pc' else web_backend)(ctx.config or {}, ctx.environ)
        return None if current == wanted else f'{which} control backend is {current}, not {wanted}'
    if kind in ('skills_module', 'module'):
        return None if importlib.util.find_spec(name) is not None else f'module {name} is not installed'
    return f'unknown requirement {req}'


def eligibility(neuron: Neuron, ctx: Context) -> Eligibility:
    reasons: List[str] = []
    if neuron.status != 'active':
        reasons.append(f'status is {neuron.status}')
    if neuron.side_effect_class == 'unknown':
        reasons.append('side effects unclassified (denied until reviewed)')
    if ctx.allowed_tools is not None and neuron.tool and neuron.tool not in set(ctx.allowed_tools):
        reasons.append(f'tool {neuron.tool} is not allowed in this session')
    for req in neuron.requirements:
        missing = _requirement(req, ctx)
        if missing:
            reasons.append(missing)
    if neuron.runtime == 'cloud' and ctx.privacy == 'local_private':
        reasons.append('local-private data may not go to a cloud neuron')
    if ctx.contains_secret and (neuron.runtime in NETWORK or neuron.side_effect_class == 'external_write'):
        reasons.append('the request mentions a secret; nothing that reaches the network may run')
    if ctx.contains_secret and neuron.contract != 'explicit' and neuron.side_effect_class != 'read_only':
        reasons.append('the request mentions a secret; neurons without an explicit contract may not touch it')
    if ctx.goal:
        refused = goal_refusal(ctx.goal)
        if refused:
            reasons.append(refused)
    return Eligibility(neuron.node_id, not reasons, neuron.gated, reasons)


def eligible_set(neurons: Iterable[Neuron], ctx: Context) -> Dict[str, Eligibility]:
    return {n.node_id: eligibility(n, ctx) for n in neurons}
