"""Real registry validation of all seven keyless local media recipe types."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import wave
import zipfile

from jarvis.agent_session import ReadActions
from jarvis.tools import ToolRegistry

BASE = Path(__file__).resolve().parents[2]


def main():
    actions = ReadActions(BASE, BASE)
    actions.allowed_tools = frozenset({'deerflow_free_media'})
    specs = {
        'chart': {'title': 'Offline Jarvis sample', 'labels': ['A', 'B', 'C'], 'values': [3, 7, 5]},
        'poster': {'title': 'Created locally', 'text': 'Free offline sandbox media.'},
        'pdf': {'title': 'Offline validation', 'text': 'This synthetic report uses no API or credentials.'},
        'slides': {'slides': [{'title': 'Offline sandbox', 'text': 'Free local libraries.'}, {'title': 'Verified artifacts', 'text': 'Actual file readback.'}]},
        'video': {'title': 'Jarvis local media', 'text': 'Rendered inside Docker.', 'duration': 3},
        'music': {'duration': 3},
        'narration': {'text': 'Jarvis created this audio inside an offline sandbox.', 'voice': 'am_michael'},
    }
    rows = []
    for kind, spec in specs.items():
        started = time.monotonic()
        try:
            output = ToolRegistry(actions).execute({'action': 'deerflow_free_media', 'value': kind, 'content': json.dumps(spec)}, lambda: False)
            result = json.loads(output.evidence)
            root = Path(result['artifact_directory'])
            files = [root / row['path'] for row in result['artifacts']]
            assert files and all(f.stat().st_size > 0 for f in files)
            for file in files:
                raw = file.read_bytes()
                if file.suffix == '.png': assert raw.startswith(b'\x89PNG')
                if file.suffix == '.pdf': assert raw.startswith(b'%PDF-')
                if file.suffix == '.pptx':
                    with zipfile.ZipFile(file) as archive: assert 'ppt/presentation.xml' in archive.namelist()
                if file.suffix == '.mp4': assert b'ftyp' in raw[:40]
                if file.suffix == '.wav':
                    with wave.open(str(file)) as audio: assert audio.getnframes() > audio.getframerate()
            rows.append({'kind': kind, 'ok': True, 'artifacts': result['artifacts'], 'job_id': result['job_id']})
        except Exception as exc:
            rows.append({'kind': kind, 'ok': False, 'error_type': type(exc).__name__, 'diagnostic': str(exc)[:200]})
        rows[-1]['seconds'] = round(time.monotonic() - started, 3)
    report = {'date': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        'passed': sum(r['ok'] for r in rows), 'total': len(rows), 'cases': rows,
        'scope': 'Actual production registry -> offline Docker -> literal-spec recipes; file type and nonempty output checked independently. No paid API, account, public upload or photoreal diffusion.'}
    (BASE / 'artifacts/reports/deerflow-free-media.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
