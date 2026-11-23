"""User-approved planning only. No Chrono install or package scripts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'app'
HOME = APP / '.jarvis-runtime/discovery/tools/micromamba-2.10.0-0'
URL = 'https://github.com/mamba-org/micromamba-releases/releases/download/2.10.0-0/micromamba-win-64.exe'
SHA = 'f8b4284bd4eb1134122eaf93b3ea6c7be567e596de5829e1a6f478e34e41974a'


def fetch(url, cap):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Jarvis-approved-Chrono-planning'}), timeout=30) as r:
        body = r.read(cap + 1)
    if len(body) > cap:
        raise ValueError('download cap exceeded')
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--resume-preflight', action='store_true')
    args = parser.parse_args()
    if not args.run:
        print('Planning disabled; explicit --run required')
        return
    HOME.mkdir(parents=True, exist_ok=True)
    if not args.resume_preflight:
        with (HOME / 'planning-started.json').open('x', encoding='utf-8') as f:
            json.dump({'approval': '2026-11-05 planning only', 'package_install': False}, f)
    elif not (HOME / 'planning-started.json').is_file() or (HOME / 'dry-run-argv.json').exists():
        raise ValueError('Resume allowed only before the one dry-run attempt')
    # Official source license is inspected before executing the pinned binary.
    license_url = 'https://raw.githubusercontent.com/mamba-org/mamba/2.10.0/LICENSE'
    license_body = (HOME / 'LICENSE-mamba.txt').read_bytes() if args.resume_preflight else fetch(license_url, 100_000)
    if not args.resume_preflight:
        (HOME / 'LICENSE-mamba.txt').write_bytes(license_body)
    text = license_body.decode('utf-8')
    if 'Redistribution and use in source and binary forms' not in text or 'CONTRIBUTORS' not in text:
        raise ValueError('expected BSD license not recognized; execution refused')
    binary = HOME / 'micromamba.exe'
    body = binary.read_bytes() if args.resume_preflight else fetch(URL, 15_000_000)
    if len(body) != 11_723_264 or hashlib.sha256(body).hexdigest() != SHA:
        raise ValueError('official binary size/hash mismatch')
    if not args.resume_preflight:
        with binary.open('xb') as f:
            f.write(body)
    sys.path.insert(0, str(APP))
    from jarvis.repo_acquisition import environment
    from jarvis.harness_process import OwnedJob, hidden_spawn
    import tempfile
    def run(args, timeout=15, cancelled=lambda: False):
        env = environment()
        profile = HOME / 'empty-profile'
        profile.mkdir(exist_ok=True)
        env['USERPROFILE'] = str(profile)
        job = OwnedJob()
        process = None
        try:
            with tempfile.TemporaryFile() as output:
                process = hidden_spawn(job, subprocess.Popen)([str(binary), '--no-rc', *args],
                    env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=output)
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    if time.monotonic() > deadline or cancelled() or os.fstat(output.fileno()).st_size > 8_000_000:
                        raise ValueError('owned planner time/disk/output cap reached; no replay')
                    time.sleep(.2)
                output.seek(0)
                raw = output.read(8_000_001)
                if process.returncode:
                    raise ValueError('planner exit: ' + raw.decode(errors='replace')[-1000:])
                return raw
        finally:
            job.close()
            if process is not None:
                process.wait(timeout=5)
    (HOME / 'version.txt').write_bytes(run(['--version']))
    help_body = run(['create', '--help'])
    (HOME / 'create-help.txt').write_bytes(help_body)
    for flag in (b'--dry-run', b'--platform', b'--root-prefix'):
        if flag not in help_body:
            raise ValueError('required CLI flag missing')
    metadata = HOME / 'metadata-root'
    argv = ['--root-prefix', str(metadata), 'create', '--dry-run', '--json', '--yes',
            '--prefix', str(HOME / 'planned-env-not-installed'), '--platform', 'win-64',
            '--override-channels', '-c', 'projectchrono/label/release', '-c', 'conda-forge',
            'python=3.12', 'pychrono=10.0.0']
    (HOME / 'dry-run-argv.json').write_text(json.dumps(argv, indent=2), encoding='utf-8')
    started = time.monotonic()
    cap_seen = False
    def cancelled():
        nonlocal cap_seen
        size = sum(p.stat().st_size for p in metadata.rglob('*') if p.is_file()) if metadata.exists() else 0
        cap_seen = size > 200_000_000
        return cap_seen
    result = {'solver_installed': False, 'binary_sha256': SHA, 'license_url': license_url}
    try:
        raw = run(argv, timeout=120, cancelled=cancelled)
        (HOME / 'dry-run.json').write_bytes(raw)
        plan = json.loads(raw)
        rows = plan.get('actions', {}).get('FETCH', [])
        result.update(success=plan.get('success', False), package_count=len(rows),
                      package_download_bytes=sum(r.get('size', 0) for r in rows),
                      packages=[{k:r.get(k) for k in ('name','version','build','size','sha256','md5','license','url','channel')} for r in rows])
    except Exception as exc:
        result.update(success=False, error=type(exc).__name__ + ': ' + str(exc)[:1000])
    result.update(seconds=time.monotonic()-started, metadata_cap_exceeded=cap_seen)
    (HOME / 'planning-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'packages'}))


if __name__ == '__main__':
    main()
