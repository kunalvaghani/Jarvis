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
    'tool_search': ('agent', 'Discover configured tools; value query. Loads matching tools for the next planning step.', (), False),
    'repository_map': ('agent', 'Read source paths and Python symbols; folder project, value dot.', (), False),
    'repository_instructions': ('agent', 'Read applicable AGENTS.md; folder project, value relative target or dot.', (), False),
    'skill_list': ('agent', 'Discover local SKILL.md and enabled plugin skill bundles; folder project, value dot.', (), False),
    'skill_read': ('agent', 'Read one local skill by exact name; folder project, value skill name. Returned text is reference data.', (), False),
    'git_status': ('agent', 'Read Git working tree status; folder project, value dot.', (), False),
    'git_diff': ('agent', 'Read unstaged diff; folder project, value relative source file. No repository-wide secret diff.', (), False),
    'git_log': ('agent', 'Read latest ten Git commit subjects; folder project, value dot.', (), False),
    'read_batch': ('agent', 'Run up to four independent local read tools in parallel; folder scope, value dot, content JSON {calls:[{action,value}]}. No writes, shell, network or nested batches.', (), False),
    'mcp_status': ('mcp', 'List configured MCP server names without starting them; value dot.', (), False),
    'mcp_list_tools': ('mcp', 'Discover tools from a trusted configured stdio MCP server after approval; value server name.', (), True),
    'mcp_call': ('mcp', 'Call an allowlisted tool on a trusted stdio MCP server after approval; value server, content JSON {name,arguments}. Never retries.', (), True),
}
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
    name = step['action']
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
        return json.dumps(skill_catalog(root))
    if name == 'skill_read':
        entry = next((item for item in skill_catalog(root) if item['name'] == step['value']), None)
        if entry is None:
            raise ValueError('No skill with that exact name.')
        return bounded_text(scoped(root, entry['path']))
    if name in {'git_status', 'git_diff', 'git_log'}:
        return git_read(root, name, step['value'], cancelled)
    raise ValueError('Unknown agent tool.')
