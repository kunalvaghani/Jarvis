"""Check read-only sessions in a synthetic temporary project; --live uses Ollama."""
import argparse
import json
from pathlib import Path
import tempfile

from jarvis.agent_session import AgentSession, OllamaProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='jarvis-agent-check-') as directory:
        base = Path(directory)
        project = base / 'demo'
        project.mkdir()
        (project / 'greet.py').write_text('def greet():\n    return "hello from the fixture"\n', encoding='utf-8')
        (project / 'AGENTS.md').write_text('Inspect source before describing it. Preserve files.', encoding='utf-8')
        before = {path.name: path.read_bytes() for path in project.iterdir()}
        session = AgentSession(base, project)
        def fixture(context):
            if not context['completed']:
                return {'final': '', 'calls': [{'action': 'read_file', 'value': 'greet.py'}]}
            return {'final': 'greet returns hello from the fixture', 'calls': []}
        provider = OllamaProvider() if args.live else fixture
        answer = session.run('Read greet.py and tell me the exact string greet returns.', provider, max_steps=6)
        if 'hello from the fixture' not in answer or before != {path.name: path.read_bytes() for path in project.iterdir()}:
            raise ValueError('The session did not inspect the source correctly or changed project files.')
        resumed = AgentSession(base, project, session.identifier)
        if len(resumed.history) != len(session.history):
            raise ValueError('Saved session could not be resumed.')
        print(json.dumps({'check': 'live-local-model' if args.live else 'fixture-provider',
                          'answer': answer, 'project_unchanged': True,
                          'session_resume': True, 'tool_calls': sum(row['event'] == 'tool.completed' for row in session.history)}, indent=2))


if __name__ == '__main__':
    main()
