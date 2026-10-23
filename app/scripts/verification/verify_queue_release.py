"""Freeze source hashes, run application regressions, and check source integrity."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'artifacts/task-queue'


def inventory():
    files=[*BASE.joinpath('jarvis').rglob('*.py'), *BASE.joinpath('tests').rglob('*.py'),
        BASE/'main.py', BASE/'config/config.json', BASE/'config/runtime_manifest.json',
        BASE/'artifacts/jarvis-audit/modules/01-architecture-inventory/source-inventory.json']
    for pattern in ('*queue*.py','*workflow*.py','live_voice_queue.py','benchmark_asr_silence.py'):
        files.extend(BASE.joinpath('scripts/verification').glob(pattern))
    return {path.relative_to(BASE).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(files)) if '__pycache__' not in path.parts}


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--fail-fast',action='store_true')
    arguments=parser.parse_args()
    OUT=arguments.output.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    before=inventory()
    write('release-source-inventory.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'sha256':before})
    with (OUT/'release-full-regression.txt').open('w',encoding='utf-8') as receipt:
        command=[sys.executable,'-m','pytest','tests','-q']+(['-x'] if arguments.fail_fast else [])
        result=subprocess.run(command,cwd=BASE,stdout=receipt,stderr=subprocess.STDOUT)
    after=inventory()
    changed=[name for name in sorted(set(before)|set(after)) if before.get(name)!=after.get(name)]
    write('release-source-integrity.json',{'checked_at':datetime.now(timezone.utc).isoformat(),
        'pytest_exit_code':result.returncode,'files':len(before),'changed':changed,'source_unchanged':not changed})
    print(json.dumps({'pytest_exit_code':result.returncode,'source_files':len(before),'changed':changed}),flush=True)
    return result.returncode or bool(changed)


if __name__=='__main__':raise SystemExit(main())
