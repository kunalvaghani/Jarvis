"""Install the pinned official SDK in its own environment; enable after readiness."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable', action='store_true', help='Select Harness planning after its runtime check passes')
    args = parser.parse_args()
    python = BASE / '.venv-harness/Scripts/python.exe'
    def run(command):
        subprocess.run([str(part) for part in command], cwd=BASE, check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if not python.is_file():
        run([sys.executable, '-m', 'venv', BASE / '.venv-harness'])
    run([python, '-m', 'pip', '--isolated', 'install', '-r', BASE / 'requirements-harness.txt'])
    run([python, '-m', 'jarvis.harness_worker', '--check'])
    if args.enable:
        path = BASE / 'config.json'
        config = json.loads(path.read_text(encoding='utf-8'))
        brain = config.setdefault('brain', {})
        brain['harness'] = {'enabled': True, 'model': brain.get('planner', 'qwen3.5:4b'), 'timeout_seconds': 180}
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('DeepSeek Harness installed; restart Jarvis to load a changed planning preference.')


if __name__ == '__main__':
    main()
