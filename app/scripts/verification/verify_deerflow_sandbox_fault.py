"""Interrupt only an owned sandbox; prove checkpoint preservation and no replay."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
import time

from jarvis.deerflow_sandbox import SandboxJob
from jarvis.docker_runtime import engine_status

BASE = Path(__file__).resolve().parents[2]


def main():
    report = {}
    with SandboxJob(BASE) as job:
        command = "python -c \"from pathlib import Path; import time; Path('/mnt/user-data/outputs/marker.txt').write_text('executed once'); time.sleep(20)\""
        errors = []
        def execute():
            try: job.execute(command, timeout=30)
            except ValueError as exc: errors.append(str(exc))
        worker = threading.Thread(target=execute)
        worker.start()
        deadline = time.monotonic() + 10
        marker = job.root / 'outputs/marker.txt'
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        if not marker.exists():
            raise ValueError('Fixture did not reach its controlled interruption point.')
        job.owned()
        job.runtime.cli(['kill', job.name], timeout=10)
        worker.join(15)
        blocked = False
        try: job.execute(command)
        except ValueError: blocked = True
        report = {'ok': bool(errors) and blocked and marker.read_text() == 'executed once' and
                   len([row for row in job.state['calls'] if row['command'] == command]) == 1,
            'state': job.state['status'], 'replay_blocked': blocked,
            'marker': marker.read_text(), 'recorded_dispatches': len(job.state['calls']),
            'docker_engine': engine_status()['status'], 'job_id': job.identifier}
    report.update(date=datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
        scope='Live deliberate stop of one attested Jarvis-owned test container during a command; shared Docker engine and unrelated containers left running. No command was repeated.')
    (BASE / 'artifacts/reports/deerflow-sandbox-fault.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
