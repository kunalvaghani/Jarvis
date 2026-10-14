"""Live real-harness tool selection through Jarvis's shared registry, synthetic source."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time

from jarvis.agent_session import ReadActions
from jarvis.tools import ToolRegistry

BASE = Path(__file__).resolve().parents[2]


def main():
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='deerflow-dynamic-') as folder:
        project = Path(folder)
        (project / 'sample.py').write_text('print(314159)\n', encoding='utf-8')
        actions = ReadActions(BASE, project, {'deerflow': {'model': 'qwen3.5:4b', 'timeout_seconds': 300}})
        actions.allowed_tools = frozenset({'deerflow_research'})
        goal = ('Find the Python module in this project, read its body and identify the literal number passed to print. '
                'Cite its relative source path. Do not run the program.')
        try:
            output = ToolRegistry(actions).execute({'action': 'deerflow_research', 'value': goal,
                'folder': str(project)}, lambda: False)
            result = json.loads(output.evidence)
            ok = ('314159' in result['answer'] and 'sample.py' in result['answer']
                  and any(r['action'] == 'read_file' and r['value'] == 'sample.py' for r in result['receipts']))
            report = {'ok': ok, 'answer': result['answer'], 'receipts': result['receipts']}
        except Exception as exc:
            report = {'ok': False, 'error': type(exc).__name__, 'diagnostic': str(exc)[:300]}
    report.update(date=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
                  seconds=round(time.monotonic() - started, 3),
                  scope='One synthetic task through Jarvis ToolRegistry -> real DeerFlow -> scoped observe/read_file -> local Qwen. No file name in goal, no pre-read, no program execution or desktop/account actions.')
    (BASE / 'artifacts/reports/deerflow-dynamic-read.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
