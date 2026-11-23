"""Run existing pytest checks without retaining assertion payloads or reading live credentials.

Usage from repo root:
  app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt post.json tests
Receipts/logs stay private in app/.jarvis-runtime/lab-validation until summarized.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'app'
sys.dont_write_bytecode = True
sys.path.insert(0, str(APP))


def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if any(path.is_relative_to(root) for root in (APP / 'secrets', APP / '.jarvis-runtime/gmail-api')):
            raise PermissionError('regression refuses production credential files')
    if event in ('socket.connect', 'socket.sendto'):
        address = args[1] if event == 'socket.connect' else args[-1]
        if isinstance(address, tuple):
            try:
                local = ipaddress.ip_address(str(address[0])).is_loopback
            except ValueError:
                local = str(address[0]) == 'localhost'
            if not local or address[1] in (11434, 9876):
                raise PermissionError('regression refuses external services and local model/Blender traffic')


def safe_id(identity):
    if '[' in identity:
        name, parameters = identity.split('[', 1)
        return name + '[param-sha256:' + hashlib.sha256(parameters.encode()).hexdigest()[:16] + ']'
    return identity


class Reports:
    def __init__(self, progress=None, source=None):
        self.reports = []
        self.collection_errors = []
        self.failure_meta = {}
        self.progress,self.source=progress,source
        self.run_id=uuid.uuid4().hex[:12]

    def checkpoint(self, event):
        if self.progress is None:return
        try:
            with self.progress.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'run_id':self.run_id,'source_sha256':self.source,**event})+'\n')
        except OSError:pass  # Observation must not alter test execution.

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed or report.skipped:
            row={'test': safe_id(report.nodeid), 'phase': report.when,
                 'outcome': report.outcome, 'seconds': report.duration}
            if report.failed:
                row.update(self.failure_meta.get((report.nodeid,report.when),{}))
                crash=getattr(report.longrepr,'reprcrash',None)
                kind=str(getattr(crash,'message','')).partition(':')[0].strip()
                row['failure_kind']=kind if re.fullmatch(r'(?:[A-Za-z_]\w*\.)*(?:[A-Z]\w*(?:Error|Exception)|TimeoutExpired)',kind) else 'assertion_or_unknown'
                try:
                    location=Path(crash.path)
                    if not location.is_absolute():location=APP/location
                    row['failure_location']=location.resolve().relative_to(APP).as_posix()+':'+str(int(crash.lineno))
                except (AttributeError,TypeError,ValueError):pass
                self.checkpoint({'event':'failure',**row})
            self.reports.append(row)
            if len(self.reports)%100==0:
                self.checkpoint({'event':'progress','reported':len(self.reports),
                    'failed':sum(r['outcome']=='failed' for r in self.reports)})

    def pytest_runtest_makereport(self,item,call):
        if call.excinfo is None:return
        error=call.excinfo.value;data={}
        for key in ('winerror','errno'):
            value=getattr(error,key,None)
            if type(value) is int:data['exception_'+key]=value
        frames=[]
        for frame in call.excinfo.traceback:
            try:
                path=Path(str(frame.path)).resolve().relative_to(APP)
                if path.parts[0] in ('jarvis','tests','scripts'):
                    frames.append(path.as_posix()+':'+str(frame.lineno+1))
            except (ValueError,AttributeError,IndexError):pass
        data['owned_stack_locations']=frames[-8:]
        # No exception messages, assertion values, locals or user paths.
        self.failure_meta[(item.nodeid,call.when)]=data

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(safe_id(report.nodeid))
            self.checkpoint({'event':'collection_error','test':safe_id(report.nodeid)})


def source_fingerprint(root=ROOT):
    root=Path(root);app=root/'app'
    h = hashlib.sha256()
    paths = [*sorted((app / 'jarvis').rglob('*.py')), *sorted((app / 'tests').rglob('*.py')),
             *sorted((app / 'config').glob('*.json')), *sorted((app / 'requirements').glob('*.txt')),
             *sorted((app / 'requirements').glob('*.json')),
             *sorted((app / 'jarvis/discovery/neurons').glob('*.json')),
             *sorted((app / 'jarvis/skills/discovery').rglob('SKILL.md')),
             *sorted((app / 'benchmarks/live').rglob('*.py')),
             *(p for p in sorted((app/'browser_extension').rglob('*')) if p.suffix in ('.py','.js','.json') and p.is_file()),
             *(p for p in (app/'main.py',app/'jarvis_bootstrap.py',root/'jarvis_bootstrap.py') if p.is_file()),
             *(root/'docs/lab'/name for name in ('run_checks.py','qualify_ah_mechanics.py','summarize_ah_regression.py'))]
    for p in paths:
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('tests', nargs='+')
    args = parser.parse_args()
    if Path(args.receipt).name != args.receipt or not args.receipt.endswith('.json'):
        raise ValueError('receipt must be one JSON filename')
    for name in args.tests:
        if not name.startswith('tests') or '..' in Path(name.split('::')[0]).parts:
            raise ValueError('select repository tests only')
    os.chdir(APP)
    out = APP / '.jarvis-runtime/lab-validation'
    out.mkdir(exist_ok=True)
    sys.addaudithook(guard)
    import pytest
    Reports.pytest_runtest_makereport=pytest.hookimpl(tryfirst=True)(Reports.pytest_runtest_makereport)
    started = time.monotonic()
    before = source_fingerprint()
    reports = Reports(out/(args.receipt[:-5]+'.progress.jsonl'),before)
    reports.checkpoint({'event':'started'})
    # Keep both pytest and unittest temporary writes inside the authorized workspace.
    # Candidate-verification subprocesses nest their own workspaces. A long
    # validation receipt prefix can exceed Windows path limits inside them.
    # Outside runtime/source ancestry: helpers must not attribute a synthetic
    # fixture's recovery logs or project discovery to the running application.
    temporary_root=ROOT/'.jtmp'/reports.run_id/'u'
    temporary_root.mkdir(parents=True)
    os.environ['TEMP']=os.environ['TMP']=str(temporary_root)
    import tempfile
    tempfile.tempdir=str(temporary_root)
    # No longrepr, captured stdout/stderr, mock call arguments or assertion values.
    code = pytest.main(['-q', '--tb=no', '-r', '', '--disable-warnings', '-p', 'no:cacheprovider',
                        '--basetemp', str(temporary_root.parent / 'p'),
                        '-o', 'faulthandler_timeout=90', *args.tests], plugins=[reports])
    passed = sum(r['phase'] == 'call' and r['outcome'] == 'passed' for r in reports.reports)
    failed = sum(r['phase'] == 'call' and r['outcome'] == 'failed' for r in reports.reports)
    skipped = sum(r['outcome'] == 'skipped' for r in reports.reports)
    errors = sum(r['phase'] != 'call' and r['outcome'] == 'failed' for r in reports.reports)
    result = {'date_local': datetime.now(timezone(timedelta(hours=5,minutes=30))).date().isoformat()+' Asia/Calcutta', 'passed': passed, 'failed': failed, 'skipped': skipped,
              'errors': errors, 'collection_errors': reports.collection_errors, 'exit_code': int(code),
              'seconds': time.monotonic() - started, 'reports': reports.reports,
              'source_sha256_before': before, 'source_sha256_after': source_fingerprint(),
              'fingerprint_scheme': 'v5: Jarvis/tests/config/requirements, Lab neurons/skills, live benchmarks, browser extension/host, app entrypoints and three verification helpers; v4 receipts retained historically',
              'isolation': 'production credential files/external network/local model and Blender traffic denied; fixture loopback allowed',
              'output_policy': 'counts and test identifiers only; no assertion payloads'}
    (out / args.receipt).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'reports'}))
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main())
