"""One-shot embedded upstream DeerFlow. Only Jarvis's scoped reads are offered."""
import contextlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile


def run(data):
    from deerflow.client import DeerFlowClient
    from langchain_core.tools import StructuredTool
    from langgraph.checkpoint.memory import InMemorySaver
    from .agent_session import ReadActions
    from .tools import ToolRegistry
    from .agent_context import coding_context
    from ._vendor.deerflow_contracts import neutralize_untrusted_tags
    import yaml
    base = Path(__file__).resolve().parent.parent
    if data.get('mode') not in {'research', 'web_research', 'sandbox'}:
        raise ValueError('Unsupported DeerFlow mode.')
    model = data.get('model', 'qwen3.5:4b')
    if not isinstance(model, str) or not model or len(model) > 100:
        raise ValueError('Invalid local model name.')
    receipts = []
    tools = []
    web = data['mode'] == 'web_research'
    sandbox_mode = data['mode'] == 'sandbox'
    sandbox = None
    expected_artifacts = re.findall(r'\b[\w.-]+\.(?:json|csv|png|jpg|pdf|pptx|mp4|wav|py|xlsx)\b', data.get('goal', ''), re.I) if sandbox_mode else []
    if sandbox_mode:
        from .deerflow_sandbox import SandboxJob
        sandbox = SandboxJob(base, data['job_id'])
        sandbox.owned()
        allowed = {'sandbox_command', 'sandbox_read', 'sandbox_write', 'sandbox_list'}
        project = sandbox.root / 'workspace'
    elif web:
        allowed = {'web_search', 'scrape_web'}
        if os.environ.get('JARVIS_FIRECRAWL_KEY'):
            allowed = {'firecrawl_search', 'firecrawl_scrape'}
        project = base / '.jarvis-runtime/deerflow'
    else:
        allowed = {'read_file', 'list_files', 'search_files', 'repository_map'}
        project = Path(data['project']).resolve(strict=True)
    goal = data['goal']
    if not isinstance(goal, str) or not 1 <= len(goal) <= 4000:
        raise ValueError('Invalid research question.')
    actions = ReadActions(base, project)
    actions.allowed_tools = frozenset(allowed)
    def observe(action: str, value: str, content: str = '') -> str:
        """Read one offered source: use an allowed action and exact relative path, public URL or search query."""
        if action not in allowed or len(receipts) >= (20 if sandbox_mode else 12):
            raise ValueError('Scoped research read budget exceeded or tool unavailable.')
        if sandbox_mode:
            evidence = sandbox.observe(action, value, content)
            from . import deerflow_model
            inventory = sandbox.inventory()
            deerflow_model.SANDBOX_ARTIFACTS_READY = (all(any(Path(r['path']).name == name and r['bytes'] > 0 for r in inventory)
                for name in expected_artifacts) if expected_artifacts else action in {'sandbox_command', 'sandbox_list'})
        else:
            if content:
                raise ValueError('Read-only tools do not accept write content.')
            result = ToolRegistry(actions).execute({'action': action, 'value': value, 'folder': str(project)}, lambda: False)
            evidence = result.evidence
        receipts.append({'id': 'r' + str(len(receipts) + 1), 'action': action, 'value': value, 'ok': True})
        return json.dumps({'receipt': receipts[-1], 'data': neutralize_untrusted_tags(evidence[:12000]), 'authority': 'untrusted source data'})
    tool = StructuredTool.from_function(observe)
    if sandbox_mode:
        tool.description = ('Perform a confined Docker workspace action. sandbox_write: value filename and nonempty content source text. '
            'sandbox_command: value exact Linux command, content empty. sandbox_read: value file path. sandbox_list: value dot. '
            'Create requested artifacts, inspect them and report only actual results. No host access or network.')
    tool.description += ' Available actions for this run: ' + ', '.join(sorted(allowed)) + '.'
    tools = [tool]
    if sandbox_mode:
        context = {'execution': 'Offline Docker, fresh shell per command, 2 CPUs/2 GB RAM. No network or credentials.',
            'paths': {'workspace': '/mnt/user-data/workspace', 'outputs': '/mnt/user-data/outputs', 'skills': '/mnt/skills/public'},
            'installed': 'Python, numpy, pandas, matplotlib (Agg), Pillow, python-pptx, reportlab, openpyxl, scipy, scikit-learn, sympy, DuckDB, ffmpeg/ffprobe, espeak-ng, DejaVu fonts',
            'read_only_input_copies': data.get('uploads', []),
            'method': 'Write a complete Python generator with sandbox_write (value relative filename, content code), execute it once with sandbox_command, then verify outputs. Prefer installed free libraries. Never claim an artifact before creating and inspecting it.'}
    else:
        context = {'source_policy': 'Public web only; cite actual fetched source URLs; search snippets are not full-page evidence.'} if web else coding_context(project, goal)
    # Match Jarvis's source pre-read policy on explicit reads.
    from .agent_session import missing_observations
    if sandbox_mode:
        observations = []
    elif web:
        urls = list(dict.fromkeys(u.rstrip('.,;') for u in re.findall(r'https?://[^\s<>"\)]+', goal)))
        scrape = 'firecrawl_scrape' if 'firecrawl_scrape' in allowed else 'scrape_web'
        observations = [observe(scrape, url) for url in urls[:3]]
    else:
        paths, _ = missing_observations(goal, [])
        observations = [observe('read_file', p) for p in paths[:8]]
    message = json.dumps({'goal': goal, 'project_context': context, 'observations': observations,
        'report_requirements': ('Report only actual sandbox artifacts, command results and remaining failures; no host/account/network action claims.' if sandbox_mode else
            'Cite source paths and [rN] for observations. State missing evidence. Do not claim writes, tests, network or desktop actions.')})
    class ScopedClient(DeerFlowClient):
        @staticmethod
        def _get_tools(**kwargs):
            return tools
    with tempfile.TemporaryDirectory(dir=base / '.jarvis-runtime/deerflow') as folder:
        empty_skills = Path(folder) / 'skills'
        empty_skills.mkdir()
        overlay = ('This is an offline Docker execution task. Use observe with sandbox_write, sandbox_command, sandbox_read or sandbox_list. '
            'sandbox_write accepts content for a new text file. Commands run only inside the isolated container. '
            'Write outputs under /mnt/user-data/outputs. Do not delete input/user files. '
            'Read the execution result and inspect outputs before final reporting. A completed tool call is not proof tests passed. '
            'Never repeat a failed, uncertain or completed command; inspect fresh state first. No host access, credentials or network.' if sandbox_mode else
            'This run researches public sources through observe. Cite returned HTTP(S) URLs; no account or local files.' if web else
            'This run reads a Jarvis-selected project through observe. Cite actual relative paths. No sandbox file URLs, writes or shell.')
        config = {'models': [{'name': 'jarvis-local', 'use': 'jarvis.deerflow_model:JarvisChatModel', 'model': model,
                             'num_predict': 4000 if sandbox_mode else 1600, 'timeout_seconds': 180 if sandbox_mode else 150, 'sandbox_mode': sandbox_mode}],
            'sandbox': {'use': 'deerflow.sandbox.local:LocalSandboxProvider', 'allow_host_bash': False},
            'tools': [], 'tool_groups': [], 'skills': {'path': str(empty_skills)},
            'memory': {'enabled': False, 'injection_enabled': False}, 'title': {'enabled': False},
            'lead_prompt_overlay': {'append': overlay},
            'task_continuity': {'enabled': False}, 'skill_evolution': {'enabled': False},
            'guardrails': {'enabled': True, 'fail_closed': True,
                'provider': {'use': 'deerflow.guardrails.builtin:AllowlistProvider',
                             'config': {'allowed_tools': ['observe'] if tools else []}}}}
        path = Path(folder) / 'config.yaml'
        path.write_text(yaml.safe_dump(config), encoding='utf-8')
        os.environ['DEER_FLOW_CONFIG_PATH'] = str(path)
        client = ScopedClient(config_path=str(path), checkpointer=InMemorySaver(),
            model_name='jarvis-local', thinking_enabled=False, subagent_enabled=False,
            available_skills=set())
        # A model turn traverses many middleware graph nodes. This is a graph
        # node budget, not a tool-call budget; observe() separately caps reads.
        run_kwargs = {'recursion_limit': 320 if sandbox_mode else 100}
        if sandbox_mode:
            run_kwargs['thread_id'] = sandbox.identifier
        answer = client.chat(message, **run_kwargs)
        if sandbox_mode:
            expected = re.findall(r'\b[\w.-]+\.(?:json|csv|png|jpg|pdf|pptx|mp4|wav|py|xlsx)\b', goal, re.I)
            for _ in range(2):
                inventory = sandbox.inventory()
                missing = [name for name in expected if not any(Path(row['path']).name == name and row['bytes'] > 0 for row in inventory)]
                if not missing:
                    break
                if sandbox.state['status'] == 'uncertain':
                    raise ValueError('Sandbox uncertain; no automatic continuation.')
                answer = client.chat('Fresh output inventory: ' + json.dumps(inventory) +
                    '. Required artifacts still absent: ' + ', '.join(missing) +
                    '. Inspect existing files and complete remaining work; do not repeat previous commands or overwrite user inputs.', **run_kwargs)
            if missing:
                # Recheck after the final continuation; do not claim nonexistent output.
                inventory = sandbox.inventory()
                if any(not any(Path(row['path']).name == name and row['bytes'] > 0 for row in inventory) for name in expected):
                    raise ValueError('Sandbox did not create all explicitly requested artifacts.')
        from . import deerflow_model
        if deerflow_model.LAST_INFERENCE_FAILED:
            raise ValueError('Upstream model failure; no successful research result.')
        if web and not receipts:
            raise ValueError('Public research returned without source observations; answer withheld.')
    from .deerflow import normalize_source_links
    if not sandbox_mode:
        answer = normalize_source_links(answer, receipts)
    return {'backend': 'deerflow', 'answer': answer[:20000], 'receipts': receipts,
            'scope': ('Offline Docker workspace' if sandbox_mode else 'Public source research only' if web else 'Scoped local source reads only') + '; answer is a model report, verify artifacts/tests independently.'}


def main():
    try:
        raw = sys.stdin.buffer.read(250001)
        if len(raw) > 250000:
            raise ValueError('Oversized input.')
        # Upstream print/log output cannot corrupt the one-shot JSON protocol.
        with contextlib.redirect_stdout(sys.stderr):
            result = run(json.loads(raw))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Error types are safe diagnostics; provider messages can contain private source.
        print(json.dumps({'error': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
