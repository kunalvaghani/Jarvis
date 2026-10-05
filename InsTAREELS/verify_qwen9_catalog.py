"""Real native choice from the configured runtime catalog; no proposal execution."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time

from jarvis.brain import validate_plan
from jarvis.knowledge_worker import session
from jarvis.native_tools import plan
from jarvis.tools import ToolRegistry
from verify_qwen9 import FixtureActions

BASE = Path(__file__).resolve().parent


if __name__ == '__main__':
    config = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
    started = time.monotonic()
    result = {'date': datetime.now(timezone.utc).isoformat(), 'model': 'qwen3.5:9b',
              'scope': 'Real inference over the configured deferred tool catalog. No desktop/API proposal was executed; not a general accuracy benchmark.'}
    with tempfile.TemporaryDirectory() as directory, session() as client:
        actions = FixtureActions(Path(directory), config)
        goal = 'Use application_search to find the configured app name for Notepad. Only propose this metadata read; do not open an app.'
        rows = ToolRegistry(actions).catalog(goal)
        result['offered_tools'] = [r['action'] for r in rows]
        try:
            proposal = plan(client, 'qwen3.5:9b', 'Choose one advertised function matching the exact user goal.',
                            {'goal': goal, 'tools': rows, 'completed': []})
            steps = validate_plan(proposal)
            result.update(passed=len(steps) == 1 and steps[0]['action'] == 'application_search', proposal=proposal)
        except Exception as exc:
            result.update(passed=False, error_type=type(exc).__name__)
    result['seconds'] = round(time.monotonic() - started, 3)
    (BASE / 'artifacts/qwen9-catalog-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
