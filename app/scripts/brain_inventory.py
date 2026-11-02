"""Phase 0 static inventory: today's capabilities as draft brain node descriptors (read-only, no Jarvis start).

    python scripts/brain_inventory.py            # writes docs/brain/inventory/*.yaml

This is a dated *snapshot*, the "before" map that Phase 1's live registry must cover. It does not drive
anything. Fields that source code does not state (side-effect class, privilege) are derived from names and
approval markers and labelled ``derived: heuristic`` for review in Phase 1. MCP tools come from the local
allowlists in ``.jarvis/mcp.json`` only: their schemas need a live ``tools/list`` (server start = host approval).
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

import yaml

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
OUT = APP / 'docs' / 'brain' / 'inventory'

TOKEN = r'(?:^|_)(?:{})(?:_|$)'
READ = re.compile(TOKEN.format('read|list|lists|search|get|inspect|status|find|check|describe|show|query|lookup|details|'
                               'map|log|diff|explain|health|ledger|instructions|tracks|albums|chapters|episodes|artists|'
                               'profile|devices|top|projects|files|methods|scrape|think|review|feedback|parse|videos|'
                               'playlists|playlist|capability|knowledge|application|repository|research|web|mcp_list'), re.I)
DESTRUCTIVE = re.compile(TOKEN.format('delete|remove|trash|purge|destroy|uninstall|drop'), re.I)
EXTERNAL = re.compile(TOKEN.format('send|post|reply|tweet|publish|email|gmail|slack|jira|github|calendar|apollo|issue|'
                                   'comment|purchase|order|pay|pull_request'), re.I)
CONTROL = re.compile(TOKEN.format('next|previous|seek|shuffle|repeat|resume|toggle|queue|transfer|mute|scroll|shortcut|'
                                  'navigate|dialog|close|browse|media|control|volume|play|pause|skip|command'), re.I)
WRITE = re.compile(TOKEN.format('create|modify|append|write|save|set|update|edit|act|type|click|select|fill|move|rename|'
                                'copy|open|launch|run|install|apply|promote|rollback|start|stop|add|commit|expand|record|'
                                'ingest|learn|lifecycle|improve|sandbox'), re.I)
OPERATION_TOOLS = {'office_xlsx', 'office_docx', 'pdf_document', 'office_automation', 'blender_task', 'unreal_task',
                   'vscode_cli', 'strategy_execute', 'deerflow_sandbox_task', 'deerflow_free_media'}


def side_effect(name: str, approval: str = 'none') -> str:
    if name in OPERATION_TOOLS:
        return 'operation_dependent'  # read or write per its operation argument; split into nodes in Phase 1.
    if DESTRUCTIVE.search(name):
        return 'destructive'
    if EXTERNAL.search(name) and (approval != 'none' or WRITE.search(name)):
        return 'external_write'
    if CONTROL.search(name):
        return 'ui_or_media_state'
    if WRITE.search(name) or approval != 'none':
        return 'local_write'
    if READ.search(name):
        return 'read_only'
    return 'unknown'


def node(node_id: str, kind: str, capability: str, provider: str, effect: str, *, privilege: str,
         source: str, note: str = '', **extra: Any) -> Dict[str, Any]:
    row = {'node_id': f'{node_id}@v1', 'kind': kind, 'capability': capability, 'provider': provider,
           'input_schema': 'TBD (Phase 1)', 'output_schema': 'TBD (Phase 1)',
           'runtime': extra.pop('runtime', 'local'), 'privilege': privilege,
           'privacy': extra.pop('privacy', 'local_private'), 'side_effect_class': effect,
           'requirements': extra.pop('requirements', []), 'resource_cost': extra.pop('resource_cost', {'gpu_vram_mb': 0}),
           'timeout_ms': extra.pop('timeout_ms', None), 'concurrency_limit': extra.pop('concurrency_limit', None),
           'version': 1, 'healthcheck': extra.pop('healthcheck', None), 'status': 'inventoried',
           'source': source, 'derived': 'heuristic: side_effect_class, privilege'}
    if note:
        row['note'] = note
    row.update(extra)
    return row


def tools() -> List[Dict[str, Any]]:
    from jarvis.tools import SPECS
    rows = []
    for spec in SPECS:
        effect = side_effect(spec.name, spec.approval)
        privilege = 'approval_required' if spec.approval != 'none' else ('read' if effect == 'read_only' else 'write')
        network = spec.backend in ('toolkit', 'browser', 'realtime') or spec.name.startswith('web_')
        rows.append(node(f'tool.{spec.backend}.{spec.name}', 'tool', f'{spec.backend}.{spec.name}',
                         f'jarvis.tools.ToolRegistry ({spec.backend})', effect, privilege=privilege,
                         source='jarvis/tools.py SPECS', runtime='local_or_network' if network else 'local',
                         privacy='public_data_only' if spec.backend == 'browser' else 'local_private',
                         description=spec.description[:300]))
    return rows


def methods() -> List[Dict[str, Any]]:
    from jarvis.execution_strategy import METHODS
    rows = []
    for method in METHODS:
        writes = bool(set(method.operations) - {'read', 'inspect', 'text'})
        rows.append(node(f'method.{method.id}', 'tool', f'{method.domain}.{"/".join(sorted(method.operations))}',
                         f'jarvis.execution_strategy ({method.tool})', 'local_write' if writes else 'read_only',
                         privilege='approval_required' if writes else 'read', source='jarvis/execution_strategy.py METHODS',
                         requirements=list(method.requires), timeout_ms=None, tier=method.tier,
                         verification=method.verification, expected_latency_ms=method.latency_ms, cost=method.cost,
                         targets=sorted(method.targets), unsafe_write_features=sorted(method.unsafe_write_features)))
    return rows


def mcp() -> List[Dict[str, Any]]:
    path = APP / '.jarvis' / 'mcp.json'
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    servers = data.get('servers') or data.get('mcpServers') or data
    rows = []
    for server, spec in sorted(servers.items()):
        if not isinstance(spec, dict):
            continue
        for tool in sorted(spec.get('allow_tools', [])):
            rows.append(node(f'mcp.{server}.{tool}', 'mcp', f'{server}.{tool}', f'jarvis.mcp_bridge ({server})',
                             side_effect(tool), privilege='approval_required', source='.jarvis/mcp.json allow_tools',
                             runtime='local_or_network', requirements=[f'mcp_server:{server}'],
                             healthcheck='mcp_status', enabled=bool(spec.get('enabled')), trusted=bool(spec.get('trusted')),
                             note='Schema needs a live tools/list (server start needs host approval).'))
    return rows


def routes() -> List[Dict[str, Any]]:
    fixed = [
        ('route.calculator', 'calculator.arithmetic', 'jarvis.fast_routes', 'local_write', 'Calculator typed once, display checked'),
        ('route.web_question', 'web.answer_from_page', 'jarvis.fast_routes', 'read_only', 'page read in full; numbers grounded'),
        ('route.small_program', 'code.create_single_file', 'jarvis.small_program', 'local_write', 'reference program agreement'),
        ('route.small_edit', 'code.edit_single_file', 'jarvis.small_edit', 'local_write', 'reference output and function agreement'),
        ('route.web_app', 'code.web_app', 'jarvis.web_app', 'local_write', 'headless browser checks and repair'),
        ('route.blender_live', '3d.live_model', 'jarvis.blender_live', 'local_write', 'sealed blender_scene verifier'),
    ]
    rows = [node(i, 'skill', c, p, e, privilege='write', source='upgrade v2 Phase 1 fixed routes', note=n,
                 requirements=['flag:control.api_routes']) for i, c, p, e, n in fixed]
    from jarvis.learning.verifiers import REGISTRY
    rows += [node(f'verifier.{name}', 'verifier', f'verify.{name}', f'jarvis.learning.verifiers ({module})', 'read_only',
                  privilege='read', source='jarvis/learning/verifiers REGISTRY (sealed)') for name, (module, _) in REGISTRY.items()]
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    groups = {'tools': tools(), 'methods': methods(), 'mcp': mcp(), 'routes_and_verifiers': routes()}
    summary: Dict[str, Any] = {'generated': date.today().isoformat(), 'kind': 'static snapshot (Phase 0)', 'groups': {}}
    for name, rows in groups.items():
        header = {'generated': date.today().isoformat(), 'snapshot': True, 'nodes': rows}
        (OUT / f'{name}.yaml').write_text(yaml.safe_dump(header, sort_keys=False, allow_unicode=True, width=120),
                                          encoding='utf-8')
        effects: Dict[str, int] = {}
        for row in rows:
            effects[row['side_effect_class']] = effects.get(row['side_effect_class'], 0) + 1
        summary['groups'][name] = {'nodes': len(rows), 'side_effect_classes': effects}
    ids = [row['node_id'] for rows in groups.values() for row in rows]
    summary['total_nodes'] = len(ids)
    summary['duplicate_ids'] = sorted({i for i in ids if ids.count(i) > 1})
    (OUT / 'SUMMARY.yaml').write_text(yaml.safe_dump(summary, sort_keys=False), encoding='utf-8')
    print(yaml.safe_dump(summary, sort_keys=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
