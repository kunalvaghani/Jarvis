"""Alita-inspired MCP synthesis for genuine ToolRegistry capability gaps.

Original Jarvis implementation inspired by the published Alita architecture
(arXiv 2505.20286: "MCP creation" by brainstorming, script generation, virtual
environment execution and MCP packaging). The public CharlesQ9/Alita repository
contains no source code, so nothing is ported from it.

Pipeline: discover existing authorized tools -> accept a typed spec whose
mechanism is an allowlisted Python standard-library module -> generate a minimal
typed server from a fixed template on the official MCP Python SDK (mcp==2.3.0,
MIT) -> AST policy screen -> test in the reviewed container (no network,
read-only root, no capabilities, non-root, PID/memory/CPU limits, lifetime fence)
-> register as a provisional generated server only after runtime approval.
A virtual environment is not used as a sandbox; Docker isolation is required.

Generated code never receives host files (only its own server.py is mounted
read-only), secrets, network access or the registry/approval files. Every call
still goes through mcp_bridge with exact allowlists and per-call approval.
"""
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import threading
import time
import uuid

IMAGE = 'jarvis-mcp-runtime:1'
IMAGE_LABEL = 'org.jarvis.mcp-runtime'
CONTAINER_LABEL = 'org.jarvis.mcp-generated'
HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
ALLOWED_MODULES = frozenset({'hashlib', 'math', 'statistics', 'json', 're', 'datetime', 'decimal', 'fractions',
                             'unicodedata', 'base64', 'binascii', 'string', 'textwrap', 'itertools', 'collections',
                             'csv', 'io', 'uuid', 'zlib', 'difflib', 'calendar', 'colorsys'})
FORBIDDEN_NAMES = frozenset({'eval', 'exec', 'compile', 'open', '__import__', 'globals', 'locals', 'vars', 'getattr',
                             'setattr', 'delattr', 'input', 'breakpoint', 'help', 'exit', 'quit', 'memoryview',
                             'classmethod', 'staticmethod', 'super', 'type', 'object'})
TYPES = {'str': 'str', 'int': 'int', 'float': 'float', 'bool': 'bool', 'list[str]': 'list[str]',
         'list[float]': 'list[float]', 'list[int]': 'list[int]', 'dict': 'dict'}
JSON_TYPES = {'str': 'string', 'int': 'integer', 'float': 'number', 'bool': 'boolean', 'list[str]': 'array',
              'list[float]': 'array', 'list[int]': 'array', 'dict': 'object'}
SLUG = re.compile(r'[a-z][a-z0-9_]{2,40}')
_LOCK = threading.Lock()


def generated_root(base):
    return Path(base) / '.jarvis-runtime' / 'mcp' / 'generated'


def registry_path(base):
    return generated_root(base) / 'registry.json'


# ---- 1. discovery ------------------------------------------------------------------------------------------------------
def discover_existing(actions, need, limit=5):
    """Existing registry tools, configured MCP tools and skills that may already cover the need."""
    from .tools import ToolRegistry
    from .capabilities import tokens
    found = []
    words = tokens(need)
    for row in ToolRegistry(actions).search(need, limit):
        overlap = len(words & tokens(row['action'].replace('_', ' ') + ' ' + row.get('description', '')))
        if overlap >= max(2, len(words) // 2):
            found.append({'kind': 'tool', 'name': row['action'], 'overlap': overlap})
    try:
        from .mcp_bridge import configurations
        for server, config in configurations(Path(actions.base)).items():
            for tool in config.get('allow_tools', []):
                overlap = len(words & tokens(tool.replace('_', ' ')))
                if overlap >= max(1, len(words) // 2):
                    found.append({'kind': 'mcp', 'name': server + ':' + tool, 'overlap': overlap})
    except (OSError, ValueError):
        pass
    return sorted(found, key=lambda row: -row['overlap'])


# ---- 2/3. spec and generation ------------------------------------------------------------------------------------------
def validate_spec(spec):
    if not isinstance(spec, dict) or set(spec) - {'name', 'description', 'parameters', 'returns', 'mechanism',
                                                  'implementation', 'tests', 'timeout_seconds'}:
        raise ValueError('Spec has unknown or missing fields.')
    name = spec.get('name')
    if not isinstance(name, str) or not SLUG.fullmatch(name):
        raise ValueError('Tool name must be a lowercase identifier.')
    if not isinstance(spec.get('description'), str) or not 10 <= len(spec['description']) <= 300 or '"""' in spec['description']:
        raise ValueError('Description must be 10-300 characters.')
    parameters = spec.get('parameters')
    if (not isinstance(parameters, dict) or not 1 <= len(parameters) <= 8 or
            any(not SLUG.fullmatch(k) or v not in TYPES for k, v in parameters.items())):
        raise ValueError('Parameters must map identifiers to supported types.')
    if spec.get('returns') not in TYPES:
        raise ValueError('Unsupported return type.')
    modules = spec.get('mechanism')
    if not isinstance(modules, list) or not modules or not set(modules) <= ALLOWED_MODULES:
        raise ValueError('Mechanism must be allowlisted standard-library modules: ' + ', '.join(sorted(ALLOWED_MODULES)))
    if not isinstance(spec.get('implementation'), str) or not 1 <= len(spec['implementation']) <= 4000:
        raise ValueError('Implementation body must be 1-4000 characters.')
    tests = spec.get('tests')
    if not isinstance(tests, list) or not 2 <= len(tests) <= 20:
        raise ValueError('Provide 2-20 test vectors, including at least one expected error.')
    if not any(t.get('error') is True for t in tests if isinstance(t, dict)):
        raise ValueError('Include an invalid-input test that must report an error.')
    for test in tests:
        if not isinstance(test, dict) or not isinstance(test.get('arguments'), dict) or not ('expected' in test or test.get('error') is True):
            raise ValueError('Each test needs arguments and expected or error.')
    timeout = spec.get('timeout_seconds', 10)
    if type(timeout) not in {int, float} or not 2 <= timeout <= 30:
        raise ValueError('Timeout must be 2-30 seconds.')
    return spec


def generate(spec):
    """Fixed template: only the function body comes from the spec."""
    spec = validate_spec(spec)
    signature = ', '.join(f'{k}: {TYPES[v]}' for k, v in spec['parameters'].items())
    body = '\n'.join('    ' + line if line.strip() else '' for line in spec['implementation'].strip('\n').splitlines())
    imports = '\n'.join(f'import {module}' for module in sorted(set(spec['mechanism'])))
    return (f'"""Generated by Jarvis MCP synthesis. Provisional; network-less container only."""\n'
            f'{imports}\nfrom mcp.server.mcpserver import MCPServer\n\n'
            f'mcp = MCPServer("jarvis-generated-{spec["name"]}")\n\n\n'
            f'@mcp.tool()\ndef {spec["name"]}({signature}) -> {TYPES[spec["returns"]]}:\n'
            f'    """{spec["description"]}"""\n{body}\n\n\n'
            f'if __name__ == "__main__":\n    mcp.run()\n')


# ---- 4. static policy --------------------------------------------------------------------------------------------------
def screen(source, spec):
    """AST allowlist: generated code may compute, not reach files, processes, network or interpreter internals."""
    if len(source.encode('utf-8')) > 8000:
        raise ValueError('Generated server exceeds 8 KB.')
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError('Generated code does not parse: ' + str(exc)[:120]) from None
    allowed_modules = set(spec['mechanism'])
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or functions[0].name != spec['name']:
        raise ValueError('Generated module must define exactly the declared tool function.')
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_modules or alias.asname:
                    raise ValueError('Import not allowed: ' + alias.name)
        elif isinstance(node, ast.ImportFrom):
            if not (node.module == 'mcp.server.mcpserver' and [a.name for a in node.names] == ['MCPServer']):
                raise ValueError('Import not allowed: ' + str(node.module))
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError('Forbidden name: ' + node.id)
        elif isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError('Private or dunder attribute access is not allowed: ' + node.attr)
        elif isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.ClassDef, ast.Await)):
            raise ValueError('Statement not allowed in generated tools: ' + type(node).__name__)
        elif isinstance(node, ast.Name) and node.id.startswith('__') and node.id != '__name__':
            raise ValueError('Dunder names are not allowed: ' + node.id)
    inner = ast.walk(functions[0])
    if any(isinstance(n, ast.FunctionDef) and n is not functions[0] for n in inner):
        raise ValueError('Nested function definitions are not allowed.')
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


# ---- 5. container ------------------------------------------------------------------------------------------------------
def image_status(cancelled=lambda: False):
    from .repo_sandbox import RepositorySandbox
    sandbox = RepositorySandbox(IMAGE)
    try:
        image = json.loads(sandbox.cli(['image', 'inspect', IMAGE], cancelled, 20))[0]
    except (ValueError, IndexError, KeyError) as exc:
        return {'available': False, 'reason': 'MCP runtime image missing; run scripts/setup/setup_mcp_runtime.py (' + str(exc)[:120] + ')'}
    labels = image.get('Config', {}).get('Labels') or {}
    if image.get('Os') != 'linux' or labels.get(IMAGE_LABEL) != '1' or not re.fullmatch(r'sha256:[a-f0-9]{64}', image.get('Id', '')):
        return {'available': False, 'reason': 'MCP runtime image is not the reviewed labelled Linux image.'}
    return {'available': True, 'image_id': image['Id'], 'sdk': labels.get('org.jarvis.mcp-sdk')}


def server_config(server, folder, tool, image_id, timeout):
    docker = shutil.which('docker')
    if not docker:
        raise ValueError('Docker CLI unavailable; generated MCP servers cannot run.')
    source = (Path(folder) / 'server.py').resolve()
    if ',' in str(source):
        raise ValueError('Generated server path cannot contain commas.')
    args = ['--host', HOST, 'run', '-i', '--rm', '--pull', 'never', '--label', CONTAINER_LABEL + '=' + server,
            '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--pids-limit', '32', '--memory', '256m', '--memory-swap', '256m', '--cpus', '0.5',
            '--user', '65534:65534', '--log-driver', 'none', '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m',
            '--mount', 'type=bind,src=' + str(source) + ',dst=/server.py,readonly',
            '--env', 'HTTP_PROXY=', '--env', 'HTTPS_PROXY=', '--env', 'ALL_PROXY=',
            # Lifetime fence inside the container, independent of the client deadline.
            '--entrypoint', '/usr/bin/timeout', image_id, '--kill-after=2', '120', '/usr/local/bin/python', '-I', '-B', '/server.py']
    return {'command': str(Path(docker).resolve()), 'args': args, 'trusted': True, 'enabled': True, 'allow_tools': [tool],
            'timeout_seconds': max(20, int(timeout) + 15)}


def reap(server, cancelled=lambda: False):
    """Remove only containers labelled for this generated server."""
    from .repo_sandbox import RepositorySandbox
    sandbox = RepositorySandbox(IMAGE)
    ids = sandbox.cli(['ps', '-aq', '--filter', 'label=' + CONTAINER_LABEL + '=' + server], cancelled, 20).decode().split()
    for identifier in ids:
        try:
            sandbox.cli(['rm', '-f', identifier], cancelled, 20)
        except ValueError:
            pass
    return len(ids)


def _equal(actual, expected):
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9)
        except (TypeError, ValueError):
            return False
    return actual == expected


def run_tests(base, config, spec, cancelled=lambda: False):
    """Real MCP handshake and calls against the generated server inside the container."""
    from .mcp_bridge import StdioClient
    client = StdioClient(config, Path(base), cancelled)
    started = time.monotonic()
    results = []
    try:
        client.initialize()
        tools = client.tools()
        if [t.get('name') for t in tools] != [spec['name']]:
            raise ValueError('Server advertised unexpected tools: ' + str([t.get('name') for t in tools])[:200])
        schema = tools[0].get('inputSchema', {})
        properties = schema.get('properties', {})
        if set(properties) != set(spec['parameters']) or any(
                properties[k].get('type') != JSON_TYPES[v] for k, v in spec['parameters'].items()):
            raise ValueError('Advertised input schema does not match the typed spec.')
        for test in spec['tests']:
            result = client.request('tools/call', {'name': spec['name'], 'arguments': test['arguments']})
            error = result.get('isError') is True
            structured = result.get('structuredContent') or {}
            value = structured if spec['returns'] == 'dict' and 'result' not in structured else structured.get('result')
            passed = error if test.get('error') else (not error and _equal(value, test['expected']))
            results.append({'arguments_keys': sorted(test['arguments']), 'expected_error': bool(test.get('error')),
                            'is_error': error, 'passed': passed})
            if not passed:
                raise ValueError('Generated tool failed a test vector.')
    finally:
        client.close()
    return {'tests': results, 'seconds': round(time.monotonic() - started, 3), 'tool': tools[0]}


# ---- 7/8. registry -----------------------------------------------------------------------------------------------------
def load_registry(base):
    path = registry_path(base)
    if not path.is_file():
        return {'version': 1, 'servers': {}, 'history': []}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('servers'), dict):
        raise ValueError('Generated MCP registry is damaged; preserved for review.')
    return data


def save_registry(base, data):
    path = registry_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.registry-' + uuid.uuid4().hex[:8])
    temporary.write_text(json.dumps(data, indent=1), encoding='utf-8')
    from .checkpoint_io import replace_checkpoint
    replace_checkpoint(temporary, path, path.parent)


def synthesize(actions, need, author, cancelled=lambda: False):
    """Fill a genuine capability gap with a tested, approved, provisional MCP tool."""
    existing = discover_existing(actions, need)
    if existing:
        return {'status': 'existing', 'matches': existing}
    spec = author(need)
    source = generate(spec)
    digest = screen(source, spec)
    status = image_status(cancelled)
    if not status['available']:
        from .tool_errors import ToolUnavailable
        raise ToolUnavailable(status['reason'])
    server = 'gen-' + spec['name'].replace('_', '-')
    with _LOCK:
        registry = load_registry(actions.base)
        previous = registry['servers'].get(server)
    folder = generated_root(actions.base) / server / digest[:12]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'server.py').write_text(source, encoding='utf-8')
    (folder / 'spec.json').write_text(json.dumps(spec, indent=1), encoding='utf-8')
    config = server_config(server, folder, spec['name'], status['image_id'], spec.get('timeout_seconds', 10))
    try:
        report = run_tests(actions.base, config, spec, cancelled)
    finally:
        leftovers = reap(server, cancelled)
    actions._approve('mcp_register', json.dumps({'server': server, 'tool': spec['name'], 'code_sha256': digest,
                                                 'mechanism': spec['mechanism'], 'network': 'none',
                                                 'tests_passed': len(report['tests'])}), cancelled)
    from .mcp_contract import schema_digest
    entry = {**config, 'status': 'provisional', 'code_sha256': digest, 'image_id': status['image_id'],
             'spec_sha256': hashlib.sha256((folder / 'spec.json').read_bytes()).hexdigest(),
             'schema_sha256': schema_digest(report.pop('tool')),
             'sdk': status.get('sdk'), 'tests': report['tests'], 'need': str(need)[:300],
             'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    with _LOCK:
        registry = load_registry(actions.base)
        registry['history'] = (registry['history'] + [{'server': server, 'replaced': previous, 'at': entry['created_at']}])[-50:]
        registry['servers'][server] = entry
        save_registry(actions.base, registry)
    return {'status': 'registered', 'server': server, 'tool': spec['name'], 'trust_state': 'provisional',
            'code_sha256': digest, 'tests': report, 'containers_removed_after_tests': leftovers}


def health(actions, server, cancelled=lambda: False):
    """Re-run the stored test vectors; unhealthy servers are unregistered and the prior entry restored."""
    with _LOCK:
        registry = load_registry(actions.base)
        entry = registry['servers'].get(server)
    if entry is None:
        raise ValueError('Unknown generated server.')
    folder = Path(next(arg for arg in entry['args'] if arg.startswith('type=bind,src=')).split('src=', 1)[1].split(',', 1)[0]).parent
    spec = json.loads((folder / 'spec.json').read_text(encoding='utf-8'))
    try:
        source = (folder / 'server.py').read_text(encoding='utf-8')
        if hashlib.sha256(source.encode('utf-8')).hexdigest() != entry['code_sha256']:
            raise ValueError('Generated server code changed after approval.')
        report = run_tests(actions.base, {k: entry[k] for k in ('command', 'args', 'trusted', 'enabled', 'allow_tools',
                                                                 'timeout_seconds')}, spec, cancelled)
        from .mcp_contract import schema_digest
        pins = {'spec_sha256': hashlib.sha256((folder / 'spec.json').read_bytes()).hexdigest(),
                'schema_sha256': schema_digest(report.pop('tool'))}
        with _LOCK:
            current = load_registry(actions.base)
            if server in current['servers'] and current['servers'][server].get('code_sha256') == entry['code_sha256']:
                current['servers'][server].update(pins, status=entry.get('status') if entry.get('status') != 'drifted' else 'provisional')
                save_registry(actions.base, current)
        restored = restore_dependent_skills(getattr(actions, 'skills', None), server)
        return {'server': server, 'healthy': True, 'tests': report, 'restored_skills': restored, **pins}
    except (ValueError, OSError) as exc:
        return {'server': server, 'healthy': False, 'reason': str(exc)[:300], **unregister(actions.base, server)}
    finally:
        reap(server, cancelled)


def unregister(base, server):
    with _LOCK:
        registry = load_registry(base)
        if server not in registry['servers']:
            return {'unregistered': False}
        replaced = next((row['replaced'] for row in reversed(registry['history'])
                         if row['server'] == server and row.get('replaced')), None)
        if replaced:
            registry['servers'][server] = replaced  # restore the previously approved version
        else:
            del registry['servers'][server]
        registry['history'] = (registry['history'] + [{'server': server, 'unregistered_at':
                               datetime.now(timezone.utc).isoformat(timespec='seconds')}])[-50:]
        save_registry(base, registry)
    return {'unregistered': True, 'restored_previous': bool(replaced)}


def configurations(base):
    """Enabled generated servers for mcp_bridge (approval per call still applies)."""
    try:
        registry = load_registry(base)
    except (OSError, ValueError):
        return {}
    keys = ('command', 'args', 'trusted', 'enabled', 'allow_tools', 'timeout_seconds')
    identity = ('code_sha256', 'spec_sha256', 'schema_sha256', 'image_id')
    # The approved identity travels with the configuration so the bridge can enforce it at every call (P33-001).
    return {name: {**{k: entry[k] for k in keys}, 'generated_identity': {k: entry.get(k) for k in identity}}
            for name, entry in registry['servers'].items()
            if entry.get('enabled') is True and entry.get('status') in {'provisional', 'trusted'}}


def dependent_skills(skills, server):
    """Skills whose guidance or declared tools call this generated server."""
    rows = getattr(skills, 'catalog', None) or []
    return [row for row in rows if row.get('skill_id') and (server in str(row.get('body', ''))
                                                             or server in [str(t) for t in row.get('tools', [])])]


def invalidate_dependent_skills(skills, server):
    """Disable dependent skills until the server is revalidated; recorded so only these are restored later."""
    store = getattr(skills, 'store', None)
    names = []
    for row in dependent_skills(skills, server):
        if store is not None:
            store.set_state(row['skill_id'], enabled=False, compatibility={'disabled_by': 'mcp_drift', 'server': server})
        row['enabled'] = False
        names.append(row['name'])
    return names


def restore_dependent_skills(skills, server):
    store = getattr(skills, 'store', None)
    restored = []
    for row in dependent_skills(skills, server):
        record = store.record(row['skill_id']) if store is not None else None
        try:
            marker = json.loads((record or {}).get('compatibility_json') or '{}')
        except ValueError:
            marker = {}
        if marker == {'disabled_by': 'mcp_drift', 'server': server}:
            store.set_state(row['skill_id'], enabled=True, compatibility={})
            row['enabled'] = True
            restored.append(row['name'])
    return restored


def mark_drifted(base, server, reason, skills=None):
    """Disable a generated server whose approved identity no longer matches, and the skills that depend on it."""
    if skills is not None:
        invalidate_dependent_skills(skills, server)
    with _LOCK:
        registry = load_registry(base)
        entry = registry['servers'].get(server)
        if entry is None:
            return False
        entry['status'] = 'drifted'
        entry['drift_reason'] = str(reason)[:200]
        registry['history'] = (registry['history'] + [{'server': server, 'drifted_at':
                               datetime.now(timezone.utc).isoformat(timespec='seconds'), 'reason': str(reason)[:200]}])[-50:]
        save_registry(base, registry)
    return True


def mounted_source(config):
    return Path(next(arg for arg in config['args'] if arg.startswith('type=bind,src=')).split('src=', 1)[1].split(',', 1)[0])


def verified_execution_config(base, server, config, cancelled=lambda: False, skills=None):
    """Verify the approved identity now and return a config that mounts a private copy of the verified bytes.

    Editing the registered source after this check cannot change what runs: the container mounts the copy.
    Any mismatch disables the server (status 'drifted') before approval or launch.
    """
    identity = config.get('generated_identity') or {}
    try:
        if not all(identity.get(k) for k in ('code_sha256', 'spec_sha256', 'schema_sha256', 'image_id')):
            raise ValueError('Generated server has no pinned contract; run its health check to revalidate.')
        source = mounted_source(config)
        # Same definition as registration and health: the digest of the decoded source text.
        code = source.read_text(encoding='utf-8').encode('utf-8')
        if hashlib.sha256(code).hexdigest() != identity['code_sha256']:
            raise ValueError('Generated server code changed after approval.')
        if hashlib.sha256((source.parent / 'spec.json').read_bytes()).hexdigest() != identity['spec_sha256']:
            raise ValueError('Generated server spec changed after approval.')
        if identity['image_id'] not in config['args']:
            raise ValueError('Generated server configuration no longer pins its approved image.')
        status = image_status(cancelled)
        if not status['available'] or status['image_id'] != identity['image_id']:
            raise ValueError('Approved runtime image is unavailable or changed.')
    except (ValueError, OSError, StopIteration) as exc:
        mark_drifted(base, server, exc, skills)
        raise ValueError('Generated MCP server disabled pending revalidation: ' + str(exc)[:160]) from None
    private = Path(base) / '.jarvis-runtime' / 'mcp' / 'exec' / uuid.uuid4().hex
    private.mkdir(parents=True)
    copy = private / 'server.py'
    copy.write_bytes(code)
    if hashlib.sha256(copy.read_bytes()).hexdigest() != identity['code_sha256']:
        raise ValueError('Private execution copy failed verification.')
    args = [arg.replace('src=' + str(source) + ',', 'src=' + str(copy.resolve()) + ',') if arg.startswith('type=bind,src=')
            else arg for arg in config['args']]
    return {**config, 'args': args}, private
