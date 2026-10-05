"""Read-only development tools and controlled batches for the shared registry."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from .agent_context import scoped, bounded_text, repository_map, instruction_context, skill_catalog

TOOLS = {
    'windows_command_search': ('windows', 'Search all 493 imported Windows recipes by exact command ID or task keywords; returns required literal parameters and approval/prerequisites. Does not execute.', (), False),
    'windows_command': ('windows', 'Execute one pinned Windows recipe; value ID, content JSON literal parameters. Requires the user to request that exact ID or exact recipe name; use windows_command_search first. No arbitrary shell/Python. Effects require fresh target and approvals; result is dispatch evidence, not goal verification.', (), False),
    'integration_status': ('agent', 'Read registered tool groups, configured app/skill counts, MCP status and missing credential names. Does not start providers or expose secrets.', (), False),
    'application_search': ('agent', 'Find up to twenty configured desktop app names; value app query, or dot to list the first twenty. Uses the current catalog; does not launch anything.', (), False),
    'runtime_capabilities': ('agent', 'Select runtime tools, relevant skills and validated saved programs for value task. Reports missing configuration; performs no actions.', (), False),
    'tool_search': ('agent', 'Discover configured tools; value query. Loads matching tools for the next planning step.', (), False),
    'repository_map': ('agent', 'Read source paths and Python symbols; folder project, value dot.', (), False),
    'repository_instructions': ('agent', 'Read applicable AGENTS.md; folder project, value relative target or dot.', (), False),
    'skill_list': ('agent', 'Discover project skills; folder project, value dot. Use folder @jarvis for local/bundled custom guides, or @hermes and value query for upstream guidance.', (), False),
    'skill_read': ('agent', 'Read an exact project skill; folder project, value name. Use folder @jarvis for a local guide; @hermes for an upstream guide, content optional relative reference path. Read-only guidance.', (), False),
    'git_status': ('agent', 'Read Git working tree status; folder project, value dot.', (), False),
    'git_diff': ('agent', 'Read unstaged diff; folder project, value relative source file. No repository-wide secret diff.', (), False),
    'git_log': ('agent', 'Read latest ten Git commit subjects; folder project, value dot.', (), False),
    'read_batch': ('agent', 'Run up to four independent local read tools in parallel; folder scope, value dot, content JSON {calls:[{action,value}]}. No writes, shell, network or nested batches.', (), False),
    'mcp_status': ('mcp', 'List configured MCP server names without starting them; value dot.', (), False),
    'mcp_list_tools': ('mcp', 'Discover tools from a trusted configured stdio MCP server after approval; value server name.', (), True),
    'mcp_call': ('mcp', 'Call an allowlisted tool on a trusted stdio MCP server after approval; value server, content JSON {name,arguments}. Never retries.', (), True),
}
from .development_api import TOOLS as DEVELOPMENT_TOOLS
TOOLS.update(DEVELOPMENT_TOOLS)
READ_TOOLS = frozenset({'repository_map', 'repository_instructions', 'skill_list', 'skill_read',
                        'git_status', 'git_diff', 'git_log', 'read_file', 'list_files', 'search_files',
                        'query_resource', 'knowledge_search'})


def git_read(root, operation, value, cancelled):
    root = Path(root).resolve(strict=True)
    if operation == 'git_diff':
        path = scoped(root, value)
        if path == root or not path.is_file() or path.suffix.lower() not in {
                '.py', '.js', '.ts', '.jsx', '.tsx', '.rs', '.go', '.java', '.c', '.h', '.css', '.html', '.md'}:
            raise ValueError('Choose one visible source file for Git diff.')
        if any(p.startswith('.') for p in Path(value).parts) or re.search(
                r'secret|credential|password|private_key|access_token', value, re.I):
            raise ValueError('Sensitive and hidden files are excluded from Git diff.')
        args = ['diff', '--no-ext-diff', '--no-textconv', '--', path.relative_to(root).as_posix()]
    else:
        args = ['status', '--short', '--untracked-files=no'] if operation == 'git_status' else [
            'log', '-10', '--format=%h %s']
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1')
    if cancelled():
        raise ValueError('Read cancelled.')
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(['git', '--no-pager', '-c', 'core.fsmonitor=false',
                                    '-c', 'core.pager=cat', *args], cwd=root, env=env,
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 10
            while process.poll() is None:
                if cancelled() or time.monotonic() > deadline:
                    raise ValueError('Git observation cancelled or timed out.')
                time.sleep(.03)
            output.seek(0)
            text = output.read(12001).decode('utf-8', errors='replace')
            if process.returncode:
                raise ValueError('Git observation failed; choose an existing Git project.')
            return text[:12000] + ('\n[Git output truncated]' if len(text) > 12000 else '') or 'No changes.'
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)


def execute(actions, step, cancelled):
    if step['action'] in {'windows_command_search','windows_command'}:
        from .windows_commands import search, execute as windows_execute, parse as windows_parse
        if step['action']=='windows_command_search':
            return json.dumps(search(step['value']),ensure_ascii=False)
        ident=int(step['value'])
        task=actions.task_state.snapshot() or {}
        requested=windows_parse(task.get('goal',''))
        explicit_ids=json.loads(requested.value) if requested and requested.kind=='windows_command' else []
        if ident not in explicit_ids:
            raise ValueError('The planner cannot invent Windows command IDs; the user must request the exact recipe or ID.')
        params=json.loads(step.get('content') or '{}')
        given=json.loads(requested.extra or '{}')
        given=given.get(str(ident),{}) if len(explicit_ids)>1 else given
        if params!=given:
            raise ValueError('The planner cannot change the user-bound Windows command parameters.')
        return windows_execute(actions,[ident],params,cancelled)
    name = step['action']
    if name == 'application_search':
        from .names import rank
        apps = getattr(actions, 'apps', {})
        names = sorted(apps) if isinstance(apps, dict) else []
        matched = names if step['value'] == '.' else rank(step['value'], names)
        return json.dumps({'matches': matched[:20], 'scope': 'Configured names; executable availability is checked when opening.'})
    if name == 'integration_status':
        from .tools import ToolRegistry
        from .toolkits import status
        from .mcp_bridge import configurations
        rows = ToolRegistry(actions).catalog()
        apps = getattr(actions, 'apps', {})
        skills = getattr(actions, 'skills', None)
        guides = getattr(skills, 'catalog', [])
        configs = configurations(actions.base)
        providers = status()
        from .execution_adapters import PRIORITY
        config = getattr(actions, 'config', {})
        return json.dumps({'registered_tools': len(rows), 'tool_groups': sorted({r['backend'] for r in rows}),
            'configured_provider_tools': [r['tool'] for r in providers if r['configured']],
            'missing_provider_tools': [r['tool'] for r in providers if not r['configured']],
            'required_environment': sorted({key for r in providers if not r['configured'] for key in r['required_environment']}),
            'configured_app_names': len(apps) if isinstance(apps, dict) else 0,
            'local_guides': len(guides) if isinstance(guides, list) else 0,
            'mcp_servers': [{'name': n, 'enabled': c.get('enabled') is True, 'trusted': c.get('trusted') is True,
                             'allowlisted_tools': len(c.get('allow_tools', []))} for n, c in configs.items()],
            'codex_plugin_credentials_exported': False,
            'desktop_execution': {'priority': list(PRIORITY),
                'direct_execution': bool(config.get('agent_runtime', {}).get('direct_execution', False)),
                'mode': 'Reviewed primitives/ports in the existing UI worker; full agent frameworks are not installed',
                'fallback': 'Before dispatch only; uncertain input is never repeated',
                'source_manifest': 'integrations/execution-primitives/source-manifest.json'},
            'scope': 'Configuration/discovery only; provider reachability and account access are not established.'})
    if name in DEVELOPMENT_TOOLS:
        from .development_api import execute as development_execute
        return development_execute(actions,step,cancelled)
    if name == 'runtime_capabilities':
        from .tools import ToolRegistry
        from .capabilities import runtime_context
        rows = ToolRegistry(actions).search(step['value'])
        result = runtime_context(step['value'], rows, getattr(actions, 'skills', None),
                                 actions.memory.task_context(step['value']))
        loaded = getattr(actions, '_discovered_tools', None)
        if not isinstance(loaded, set):
            loaded = actions._discovered_tools = set()
        loaded.update(row['action'] for row in rows)
        return json.dumps(result, ensure_ascii=False)
    if name == 'tool_search':
        from .tools import ToolRegistry
        registry = ToolRegistry(actions)
        rows = registry.search(step['value'])
        loaded = getattr(actions, '_discovered_tools', None)
        if not isinstance(loaded, set):
            loaded = actions._discovered_tools = set()
        loaded.update(row['action'] for row in rows)
        return json.dumps(rows, ensure_ascii=False)
    if name.startswith('mcp_'):
        from .mcp_bridge import execute as mcp_execute
        return mcp_execute(actions, step, cancelled)
    if name in {'skill_list', 'skill_read'} and step.get('folder') == '@jarvis':
        actions.skills.refresh()
        rows = actions.skills.catalog
        if name == 'skill_read' and step['value'].startswith('development:'):
            from .development_knowledge import read
            return read(step['value'].split(':',1)[1])
        if name == 'skill_list':
            from .development_knowledge import catalog as development_catalog
            rows = rows + [{'name':'development:'+r['name'],'description':r['applicability'],'origin':'Jarvis built-in'} for r in development_catalog()]
            return json.dumps({'skills': [{k: r[k] for k in ('name', 'description', 'origin')} for r in rows], 'guide_errors': actions.skills.skill_errors}, ensure_ascii=False)
        row = next((r for r in rows if r['name'] == step['value']), None)
        if row is None:
            raise ValueError('No local Jarvis guide named ' + step['value'])
        return json.dumps({'name': row['name'], 'guidance': row['body'], 'origin': row['origin']}, ensure_ascii=False)
    if name in {'skill_list', 'skill_read'} and step.get('folder') == '@hermes':
        upstream = getattr(getattr(actions, 'skills', None), 'upstream', None)
        if upstream is None or upstream.error:
            raise ValueError('Hermes skill catalogue unavailable; enable memory.hermes_skills and run Hermes setup/catalogue refresh.')
        result = upstream.search(step['value']) if name == 'skill_list' else upstream.read(step['value'], step.get('content') or 'SKILL.md')
        return json.dumps(result, ensure_ascii=False)
    root = Path(actions._task_folder(step.get('folder', ''), cancelled)).resolve(strict=True)
    if name == 'read_batch':
        data = json.loads(step.get('content', '{}'))
        calls = data.get('calls') if isinstance(data, dict) else None
        if not isinstance(calls, list) or not 1 <= len(calls) <= 4:
            raise ValueError('A read batch needs one to four calls.')
        for call in calls:
            if not isinstance(call, dict) or set(call) != {'action', 'value'} or call['action'] not in READ_TOOLS:
                raise ValueError('Read batches accept only independent local observations.')
            if not isinstance(call['value'], str) or not call['value'] or len(call['value']) > 1000:
                raise ValueError('Each read needs a short text value.')
        from .tools import ToolRegistry
        registry = ToolRegistry(actions)
        def read(call):
            try:
                result = registry.execute({**call, 'folder': str(root)}, cancelled)
                return {'action': call['action'], 'value': call['value'], 'result': result.evidence[:2500], 'ok': True}
            except (ValueError, OSError, UnicodeError) as exc:
                return {'action': call['action'], 'value': call['value'], 'ok': False, 'error': str(exc)[:300]}
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix='jarvis-read') as pool:
            return json.dumps(list(pool.map(read, calls)), ensure_ascii=False)
    if name == 'repository_map':
        return repository_map(root)
    if name == 'repository_instructions':
        return json.dumps(instruction_context(root, None if step['value'] == '.' else step['value']))
    if name == 'skill_list':
        from .development_knowledge import catalog
        return json.dumps(skill_catalog(root) + [{'name': 'development:' + r['name'], 'description': r['applicability'], 'path': '@builtin'} for r in catalog()])
    if name == 'skill_read':
        if step['value'].startswith('development:'):
            from .development_knowledge import read
            return read(step['value'].split(':', 1)[1])
        entry = next((item for item in skill_catalog(root) if item['name'] == step['value']), None)
        if entry is None:
            raise ValueError('No skill with that exact name.')
        return bounded_text(scoped(root, entry['path']))
    if name in {'git_status', 'git_diff', 'git_log'}:
        return git_read(root, name, step['value'], cancelled)
    raise ValueError('Unknown agent tool.')
