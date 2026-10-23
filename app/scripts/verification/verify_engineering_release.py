"""Freeze relevant source/skill metadata and run the complete app regression suite."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parents[2]


def inventory():
    files = [*BASE.joinpath('jarvis').rglob('*.py'), *BASE.joinpath('tests').rglob('*.py'),
        *BASE.joinpath('skills').rglob('*.md'), *BASE.joinpath('scripts/verification').glob('*.py'),
        BASE / 'main.py', BASE / 'jarvis_bootstrap.py', BASE / 'Start Jarvis.cmd', BASE / 'Stop Jarvis.cmd',
        BASE / 'config/config.json', BASE / 'config/runtime_manifest.json',
        BASE / 'artifacts/jarvis-audit/modules/01-architecture-inventory/source-inventory.json',
        BASE / 'artifacts/jarvis-audit/modules/11-skill-selection/census.json',
        BASE / 'artifacts/engineering-judgment/upstream-review.json']
    files += [p for p in BASE.joinpath('artifacts/engineering-judgment/upstream').rglob('*') if p.is_file()]
    return {p.relative_to(BASE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(files)) if p.is_file() and '__pycache__' not in p.parts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    before = inventory()
    (out / 'source-before.json').write_text(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'sha256': before}, indent=2) + '\n')
    with (out / 'full-regression.txt').open('w', encoding='utf-8') as log:
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q'], cwd=BASE, stdout=log, stderr=subprocess.STDOUT)
    after = inventory()
    changed = [n for n in sorted(set(before) | set(after)) if before.get(n) != after.get(n)]
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'pytest_exit_code': result.returncode,
        'files': len(before), 'changed': changed, 'source_unchanged': not changed}
    (out / 'source-integrity.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    return result.returncode or bool(changed)


if __name__ == '__main__':
    raise SystemExit(main())
