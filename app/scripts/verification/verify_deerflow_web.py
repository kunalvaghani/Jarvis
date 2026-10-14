"""Live public-page research through the real DeerFlow and Jarvis tool registry."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import time

from jarvis.agent_session import ReadActions
from jarvis.tools import ToolRegistry

BASE = Path(__file__).resolve().parents[2]


def main():
    started = time.monotonic()
    actions = ReadActions(BASE, BASE / '.jarvis-runtime', {'deerflow': {'model': 'qwen3.5:4b', 'timeout_seconds': 300}})
    actions.allowed_tools = frozenset({'deerflow_web_research'})
    goal = ('Read https://www.python.org/doc/ and identify the official documentation link. '
            'Cite the source URL you read. Do not use local files.')
    try:
        output = ToolRegistry(actions).execute({'action': 'deerflow_web_research', 'value': goal}, lambda: False)
        result = json.loads(output.evidence)
        ok = ('https://docs.python.org' in result['answer'] and
              any(r['action'] in {'scrape_web', 'firecrawl_scrape'} and r['value'] == 'https://www.python.org/doc/' for r in result['receipts']))
        report = {'ok': ok, 'answer': result['answer'], 'receipts': result['receipts']}
    except Exception as exc:
        report = {'ok': False, 'error': type(exc).__name__, 'diagnostic': str(exc)[:300]}
    report.update(date=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        seconds=round(time.monotonic() - started, 3),
        scope='One live official public page through ToolRegistry -> DeerFlow -> Jarvis public fetch; no local source, account, upload, shell or desktop access.')
    (BASE / 'artifacts/reports/deerflow-web-read.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
