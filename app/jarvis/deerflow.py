"""Owned, bounded DeerFlow inference/research process; Jarvis keeps execution policy."""
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time
from .harness_process import OwnedJob

REVISION = 'a5e71751d7a9f8f4a71ca458da3984fc1284d098'
TOOLS = {
    'deerflow_status': ('deerflow', 'Inspect the pinned DeerFlow runtime and available public skill names; value dot. No service starts.', (), False),
    'deerflow_skill_read': ('deerflow', 'Read bundled DeerFlow public skill guidance; value exact skill name from deerflow_status. Guidance does not install dependencies or grant permission.', (), False),
    'deerflow_skill_search': ('deerflow', 'Find relevant DeerFlow public workflow guides by value task keywords. Guidance only; required providers are not activated.', (), False),
    'deerflow_research': ('deerflow', 'Research a scoped local project with the real DeerFlow harness and local Qwen; folder project, value question. Read-only, bounded deadline; includes source-read receipts. No shell, writes, accounts or web.', (), False),
    'deerflow_web_research': ('deerflow', 'Research a public topic with the real DeerFlow harness and Jarvis public search/page reads; value question. Uses separately configured Jarvis Firecrawl if available, else public web search. No accounts, uploads, shell or local source access.', (), False),
    'deerflow_sandbox_task': ('deerflow', 'Execute a requested coding, data-analysis or free media task in a confined offline Docker workspace using DeerFlow and local Qwen. value goal; optional content JSON {inputs:[explicit relative files]} with folder project. Input copies are read-only. Own output workspace; no host shell, credentials, network, project overwrite or automatic command replay.', (), False),
    'deerflow_free_media': ('deerflow', 'Create offline free artifacts. value chart/poster/pdf/slides/video/music/narration; content literal JSON {title,text,labels,values,slides:[{title,text}],duration:1..30,voice}. Charts/posters PNG, report PDF, PPTX, text-card MP4, procedural melody WAV or local Kokoro narration. No commercial API, photoreal diffusion or account publishing.', (), False),
}


def skill_root(base):
    return Path(base) / 'integrations/deer-flow-upstream/skills/public'


def status(base):
    base = Path(base)
    root = skill_root(base)
    manifest = base / 'integrations/deerflow/source-manifest.json'
    pinned = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
    return {'revision': REVISION, 'python_available': (base / '.venv-deerflow/Scripts/python.exe').is_file(),
            'sandbox_image': 'jarvis-deerflow-runtime:1', 'free_media': ['chart', 'poster', 'pdf', 'slides', 'video', 'music', 'narration'],
            'skills': sorted(p.name for p in root.iterdir() if p.is_dir() and not p.is_symlink() and (p / 'SKILL.md').is_file()) if root.is_dir() else [],
            'source_manifest': pinned, 'scope': 'Installation discovery; no live model or sandbox check.'}


def read_skill(base, name):
    from .agent_context import scoped, bounded_text
    if name not in status(base)['skills']:
        raise ValueError('Choose an exact public skill name from deerflow_status.')
    from ._vendor.deerflow_contracts import neutralize_untrusted_tags
    return neutralize_untrusted_tags(bounded_text(scoped(skill_root(base), name + '/SKILL.md'), 60000))


def search_skills(base, query):
    if not isinstance(query, str) or not 1 <= len(query) <= 500:
        raise ValueError('Use a short skill search query or dot for the catalog.')
    from .capabilities import tokens
    terms = tokens(query)
    rows = []
    for name in status(base)['skills']:
        text = read_skill(base, name)
        description = re.search(r'^description:\s*(.+)$', text, re.M)
        description = description[1][:1000] if description else name.replace('-', ' ')
        score = len(terms & tokens(name.replace('-', ' ') + ' ' + description))
        if score or query == '.':
            rows.append({'name': name, 'description': description, 'score': score,
                         'origin': 'DeerFlow public guide', 'read_via': 'deerflow_skill_read',
                         'notice': 'Guide availability does not establish provider/tool readiness.'})
    return sorted(rows, key=lambda r: (-r['score'], r['name']))[:23 if query == '.' else 6]


def normalize_source_links(answer, observations):
    """Resolve inherited sandbox links only to actual observed project sources."""
    from urllib.parse import unquote
    allowed = {str(r['value']).replace('\\', '/') for r in observations
               if r.get('ok') is True and r.get('action') == 'read_file'}
    def replace(match):
        relative = unquote(match[2]).replace('\\', '/')
        if relative not in allowed:
            raise ValueError('DeerFlow cited an unobserved sandbox source.')
        target = '<' + relative + '>' if ' ' in relative else relative
        return '[' + match[1] + '](' + target + ')'
    return re.sub(r'\[([^\]]*)\]\(file:///mnt/user-data/(?:workspace|uploads)/([^)]*)\)', replace, answer)


def request(base, payload, cancelled=lambda: False, timeout_seconds=180):
    base = Path(base).resolve(strict=True)
    python = base / '.venv-deerflow/Scripts/python.exe'
    if not python.is_file():
        raise ValueError('DeerFlow runtime missing; run python -m scripts.setup.setup_deerflow.')
    if type(timeout_seconds) not in {int, float} or not 5 <= timeout_seconds <= 600:
        raise ValueError('DeerFlow deadline must be between 5 and 600 seconds.')
    if cancelled():
        raise ValueError('DeerFlow cancelled before start.')
    runtime = base / '.jarvis-runtime/deerflow'
    runtime.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    if len(raw) > 250000:
        raise ValueError('DeerFlow input exceeds the bounded context size.')
    # No connector credentials or arbitrary user environment/config enter the worker.
    env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'COMSPEC'}}
    env.update(PYTHONUTF8='1', PYTHONPATH=str(base), PYTHON_DOTENV_DISABLED='1',
               DEER_FLOW_HOME=str(runtime), DEER_FLOW_PROJECT_ROOT=str(runtime))
    if payload.get('mode') == 'web_research' and os.environ.get('JARVIS_FIRECRAWL_KEY'):
        env['JARVIS_FIRECRAWL_KEY'] = os.environ['JARVIS_FIRECRAWL_KEY']
    with tempfile.TemporaryFile() as inp, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        inp.write(raw)
        inp.seek(0)
        job = OwnedJob()
        process = None
        try:
            process = subprocess.Popen([str(python), '-m', 'jarvis.deerflow_worker'], cwd=base,
                env=env, stdin=inp, stdout=out, stderr=err,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            job.attach(process)
            deadline = time.monotonic() + timeout_seconds
            while process.poll() is None:
                if cancelled() or time.monotonic() >= deadline:
                    raise ValueError('DeerFlow cancelled or deadline exceeded; no actions replayed.')
                if os.fstat(out.fileno()).st_size > 150000 or os.fstat(err.fileno()).st_size > 1000000:
                    raise ValueError('DeerFlow output budget exceeded; worker stopped.')
                time.sleep(.03)
            out.seek(0)
            data = out.read(150001)
            if len(data) > 150000:
                raise ValueError('DeerFlow returned oversized output.')
            try:
                result = json.loads(data.decode('utf-8'))
            except (ValueError, UnicodeError):
                err.seek(0)
                diagnostic = err.read(12000).decode('utf-8', errors='replace')
                for key in ('JARVIS_FIRECRAWL_KEY',):
                    if env.get(key):
                        diagnostic = diagnostic.replace(env[key], '[credential redacted]')
                (runtime / 'worker-error.log').write_text('exit_code=' + str(process.returncode) + '\nstdout=' + data.decode('utf-8', errors='replace')[:2000] + '\nstderr=' + diagnostic, encoding='utf-8')
                raise ValueError('DeerFlow worker failed before returning valid JSON (exit ' + str(process.returncode) + '); check isolated dependencies.') from None
            if process.returncode or not isinstance(result, dict) or result.get('error'):
                raise ValueError('DeerFlow failed: ' + str(result.get('error', 'worker error'))[:300])
            return result
        finally:
            try:
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
            finally:
                job.close()


def execute(actions, step, cancelled):
    if step['action'] == 'deerflow_free_media':
        from .deerflow_media import execute as media_execute
        return media_execute(actions, step, cancelled)
    if step['action'] == 'deerflow_status':
        return json.dumps(status(actions.base))
    if step['action'] == 'deerflow_skill_read':
        return read_skill(actions.base, step['value'])
    if step['action'] == 'deerflow_skill_search':
        return json.dumps(search_skills(actions.base, step['value']), ensure_ascii=False)
    if step['action'] == 'deerflow_sandbox_task':
        from .deerflow_sandbox import SandboxJob
        if not isinstance(step['value'], str) or not 1 <= len(step['value'].strip()) <= 4000:
            raise ValueError('Use one bounded sandbox task goal; no arbitrary host mounts or credentials.')
        params = json.loads(step.get('content') or '{}')
        if not isinstance(params, dict) or set(params) - {'inputs'}:
            raise ValueError('Sandbox accepts only explicit input filenames, no host mounts or network options.')
        options = getattr(actions, 'config', {}).get('deerflow', {})
        with SandboxJob(actions.base) as job:
            uploads = job.stage_inputs(actions._task_folder(step.get('folder', ''), cancelled), params['inputs']) if 'inputs' in params else []
            result = request(actions.base, {'mode': 'sandbox', 'job_id': job.identifier,
                'goal': step['value'], 'uploads': uploads, 'model': options.get('sandbox_model', 'qwen3.5:4b')}, cancelled,
                options.get('sandbox_timeout_seconds', 600))
            result.update(job_id=job.identifier, artifact_directory=str(job.root), artifacts=job.inventory())
            # The final delivery is built from disk evidence rather than the
            # model's prose, which can contradict its own correct output file.
            (job.root / 'model-report.json').write_text(json.dumps({'report': result['answer']}, ensure_ascii=False), encoding='utf-8')
            evidence = []
            for row in result['artifacts']:
                if row['path'].startswith('outputs/') and row['bytes'] > 0:
                    item = dict(row)
                    if row['path'].endswith('.json') and row['bytes'] <= 16000:
                        try:
                            from .agent_context import bounded_text
                            item['observed_json'] = json.loads(bounded_text(job.root / row['path'], 16000))
                        except (ValueError, UnicodeError):
                            item['json_parse_failed'] = True
                    evidence.append(item)
            result['artifact_evidence'] = evidence
            result['answer'] = 'Sandbox output files observed: ' + ', '.join(r['path'] for r in evidence) + '. Refer to artifact_evidence for actual JSON values; file creation does not prove arbitrary factual correctness.'
            return json.dumps(result, ensure_ascii=False)
    if step['action'] not in {'deerflow_research', 'deerflow_web_research'}:
        raise ValueError('Unknown DeerFlow tool.')
    if not isinstance(step['value'], str) or not 1 <= len(step['value'].strip()) <= 4000 or step.get('content'):
        raise ValueError('DeerFlow research accepts one question up to 4000 characters, no execution options.')
    options = getattr(actions, 'config', {}).get('deerflow', {})
    web = step['action'] == 'deerflow_web_research'
    payload = {'mode': 'web_research' if web else 'research', 'goal': step['value'],
               'model': options.get('model', 'qwen3.5:4b')}
    if not web:
        payload['project'] = str(actions._task_folder(step.get('folder', ''), cancelled))
    result = request(actions.base, payload, cancelled, options.get('timeout_seconds', 300 if web else 180))
    return json.dumps(result, ensure_ascii=False)
