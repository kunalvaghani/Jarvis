"""JSONL CLI/stdio API for read-only Jarvis sessions; no GUI or mic required."""
import argparse
import json
from pathlib import Path
import sys
import requests

from .agent_session import AgentSession, OllamaProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--goal')
    parser.add_argument('--session', help='Resume context using a returned session id')
    parser.add_argument('--model', help='Defaults to the configured Jarvis planner')
    parser.add_argument('--backend', choices=('ollama', 'harness'), default='ollama')
    parser.add_argument('--max-steps', type=int, default=12)
    parser.add_argument('--serve', action='store_true', help='Read JSONL requests: tool.list, session.info, session.fork, turn.run, team.run')
    args = parser.parse_args()
    def emit(row):
        print(json.dumps(row, ensure_ascii=False), flush=True)
    base = Path(__file__).resolve().parent.parent
    provider = None
    try:
        config = json.loads((base / 'config/config.json').read_text(encoding='utf-8'))
        model = args.model or config.get('brain', {}).get('planner', 'qwen3.5:9b')
        session = AgentSession(base, args.project, args.session, emit)
        if args.backend == 'harness':
            from .harness import HarnessProvider
            provider = HarnessProvider(base, model)
        else:
            provider = OllamaProvider(model, native_tools=config.get('brain', {}).get('native_tool_calling', False))
        if not args.serve:
            if not args.goal:
                parser.error('--goal is required unless --serve is used')
            session.run(args.goal, provider, max_steps=args.max_steps)
            return 0
        while True:
            line = sys.stdin.readline(60001)
            if not line:
                return 0
            request_id = None
            try:
                if len(line) > 60000 or not line.endswith('\n'):
                    emit({'id': None, 'error': 'Invalid oversized or unterminated JSONL request; input closed.'})
                    return 1
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError('Request must be an object.')
                request_id = request.get('id')
                method = request.get('method')
                if method == 'session.info':
                    result = {'session_id': session.identifier, 'project': str(session.actions.project), 'mode': 'read-only'}
                elif method == 'tool.list':
                    result = session.catalog()
                elif method == 'turn.run':
                    result = session.run(request.get('goal'), provider, max_steps=args.max_steps)
                elif method == 'session.fork':
                    result = {'session_id': session.fork(emit).identifier}
                elif method == 'team.run':
                    if args.backend == 'harness':
                        raise ValueError('Harness CLI runs one owned inference worker; use separate CLI sessions for independent research.')
                    result = session.research_parallel(request.get('goals'), provider)
                else:
                    raise ValueError('Unknown method; use session.info, session.fork, tool.list, turn.run or team.run.')
                emit({'id': request_id, 'result': result})
            except requests.RequestException:
                emit({'id': request_id, 'error': 'Local Ollama inference failed; no automatic retry.'})
            except (ValueError, OSError, KeyError, TypeError) as exc:
                emit({'id': request_id, 'error': str(exc)[:500]})
    except requests.RequestException:
        emit({'event': 'error', 'error': 'Local Ollama inference failed; start configured Ollama and check the model.'})
        return 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        emit({'event': 'error', 'error': str(exc)[:500]})
        return 1
    except KeyboardInterrupt:
        emit({'event': 'cancelled'})
        return 130
    finally:
        if provider is not None and hasattr(provider, 'close'):
            provider.close()


if __name__ == '__main__':
    sys.exit(main())
