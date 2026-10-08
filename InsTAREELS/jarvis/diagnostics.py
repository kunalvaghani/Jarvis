"""Read-only configured service checks; no model loads, repair or task replay."""
from pathlib import Path


def service_status(config, base):
    from .model_selection import required_models
    from .knowledge_worker import session
    required = required_models(config)
    rows = {}
    if required:
        client = session()
        try:
            response = client.get('http://127.0.0.1:11434/api/tags', timeout=(3, 5))
            response.raise_for_status()
            payload = response.json()
            models = payload.get('models') if isinstance(payload, dict) else None
            if not isinstance(models, list) or any(not isinstance(row, dict)
                    or not isinstance(row.get('name'), str) for row in models):
                raise ValueError('Invalid Ollama model inventory')
            names = {row['name'] for row in models}
            missing = sorted(required - names)
            rows['ollama'] = {'status': 'missing' if missing else 'available',
                              'required_models': sorted(required), 'missing_models': missing}
        except Exception as exc:
            # Raw HTTP errors may expose proxy credentials or signed URLs.
            rows['ollama'] = {'status': 'unavailable', 'error_type': type(exc).__name__,
                              'required_models': sorted(required)}
        finally:
            client.close()
    else:
        rows['ollama'] = {'status': 'disabled'}
    brain = config.get('brain', {})
    if brain.get('enabled') and brain.get('coding_backend') == 'codex' and brain.get('codex_workload_enabled', False):
        from .codex_workload import localgithub
        try:
            utilities, git, root = localgithub(brain)
            # Jarvis uses the local Git layer; hosted controller availability
            # is separate and is not a prerequisite for workload assembly.
            git.command(Path(base), '--version', timeout=10)
            rows['localgithub'] = {'status': 'available', 'mode': 'local_git',
                                  'hosted_services_checked': False}
        except Exception as exc:
            rows['localgithub'] = {'status': 'unavailable', 'error_type': type(exc).__name__,
                                  'mode': 'local_git', 'hosted_services_checked': False}
    else:
        rows['localgithub'] = {'status': 'disabled'}
    return rows
