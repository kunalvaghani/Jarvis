"""Real local model -> DeerFlow -> Docker -> independently checked artifacts."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import time

from jarvis.agent_session import ReadActions
from jarvis.tools import ToolRegistry

BASE = Path(__file__).resolve().parents[2]


def main():
    started = time.monotonic()
    actions = ReadActions(BASE, BASE, {'deerflow': {'sandbox_model': 'qwen3.5:4b', 'sandbox_timeout_seconds': 600}})
    actions.allowed_tools = frozenset({'deerflow_sandbox_task'})
    goal = ('In the offline sandbox create result.json and chart.png under outputs. Compute the sum of i*i for integers '
        '1 through 10000 inclusive. Independently check with n*(n+1)*(2*n+1)//6. JSON keys sum_squares and verified. '
        'Plot the first 100 square values with matplotlib. Write a generator, run it once, and inspect actual outputs before reporting. No network.')
    try:
        output = ToolRegistry(actions).execute({'action': 'deerflow_sandbox_task', 'value': goal}, lambda: False)
        result = json.loads(output.evidence)
        root = Path(result['artifact_directory'])
        data_path = next((root / r['path'] for r in result['artifacts'] if Path(r['path']).name == 'result.json'), None)
        chart_path = next((root / r['path'] for r in result['artifacts'] if Path(r['path']).name == 'chart.png'), None)
        data = json.loads(data_path.read_text()) if data_path else {}
        ok = data.get('sum_squares') == 333383335000 and data.get('verified') is True and chart_path and chart_path.read_bytes().startswith(b'\x89PNG')
        report = {'ok': bool(ok), 'data': data, 'answer': result['answer'], 'receipts': result['receipts'],
            'job_id': result['job_id'], 'artifacts': result['artifacts']}
        if chart_path and ok:
            import shutil
            shutil.copyfile(chart_path, BASE / 'artifacts/media/deerflow-sandbox-chart.png')
    except Exception as exc:
        report = {'ok': False, 'error_type': type(exc).__name__, 'diagnostic': str(exc)[:400]}
    report.update(date=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(), seconds=round(time.monotonic()-started,3),
        scope='Live Qwen/DeerFlow generation and execution inside offline Docker; exact numeric result and PNG signature graded independently, no API/account/host project effects.')
    (BASE / 'artifacts/reports/deerflow-sandbox-live.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
