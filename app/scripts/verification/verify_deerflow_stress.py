"""Hardest tested local batch: one million rows, SQL, held-out ML and seven media outputs."""
from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import shutil
import time

from jarvis.deerflow_sandbox import SandboxJob

BASE = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect-job', help='Read back an already completed fixture; never repeat its command')
    args = parser.parse_args()
    started = time.monotonic()
    try:
        if args.inspect_job:
            job = SandboxJob(BASE, args.inspect_job)
            data = json.loads((job.root / 'outputs/validation.json').read_text())
            mode = 'Saved completed-job artifact readback; no command replay.'
        else:
            job = SandboxJob(BASE)
            job.create()
            source = Path(__file__).with_name('deerflow_stress_program.py').read_text()
            job.observe('sandbox_write', 'stress.py', source)
            try:
                job.execute('python stress.py', timeout=120)
                data = json.loads((job.root / 'outputs/validation.json').read_text())
            finally:
                job.close()
            mode = 'New fixture execution and independent artifact readback.'
        assert data['rows'] == 1000000 and data['sum_squares'] == 333332833333500000
        assert data['sql_verified'] is True and data['held_out_accuracy'] > .97
        assert len(data['artifacts_verified']) == 7
        assert all((job.root / 'outputs' / name).stat().st_size > 0 for name in data['artifacts_verified'])
        shutil.copyfile(job.root / 'outputs/chart.png', BASE / 'artifacts/media/deerflow-stress-chart.png')
        report = {'ok': True, 'result': data, 'job_id': job.identifier,
            'artifacts': job.inventory(), 'image_id': job.state['image'], 'verification_mode': mode}
    except Exception as exc:
        report = {'ok': False, 'error_type': type(exc).__name__, 'diagnostic': str(exc)[:400]}
    report.update(date=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        wall_seconds=round(time.monotonic()-started,3),
        scope='Trusted synthetic load fixture through production offline Docker adapter; separate from model accuracy and live account/API tests. 2 CPUs, 2 GB RAM, no network or credentials.')
    (BASE / 'artifacts/reports/deerflow-sandbox-stress.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
