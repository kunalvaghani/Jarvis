"""Install the pinned full DeerFlow harness into a separate Python environment."""
import os
from pathlib import Path
import shutil
import subprocess

from jarvis.deerflow import REVISION

BASE = Path(__file__).resolve().parents[2]


def main():
    source = BASE / 'integrations/deer-flow-upstream'
    flags = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
    if not source.exists():
        subprocess.run(['git', 'clone', 'https://github.com/bytedance/deer-flow.git', str(source)], check=True, **flags)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', REVISION], check=True, **flags)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise ValueError('Existing DeerFlow checkout has a different revision; preserve local work and select the reviewed revision first.')
    uv = shutil.which('uv') or str(BASE / '.venv-hermes-bootstrap/Scripts/uv.exe')
    env = {**os.environ, 'UV_CACHE_DIR': str(BASE / '.jarvis-runtime/deerflow-cache'),
           'UV_PYTHON_INSTALL_DIR': str(BASE / '.jarvis-runtime/deerflow-python')}
    if not (BASE / '.venv-deerflow/Scripts/python.exe').is_file():
        subprocess.run([uv, 'venv', '--python', '3.12', str(BASE / '.venv-deerflow')], env=env, check=True, **flags)
    subprocess.run([uv, 'pip', 'install', '--python', str(BASE / '.venv-deerflow/Scripts/python.exe'),
                    '-r', 'requirements/deerflow.txt'], cwd=BASE, env=env, check=True, **flags)
    subprocess.run([str(BASE / '.venv-deerflow/Scripts/python.exe'), '-c',
                    'from deerflow.client import DeerFlowClient; print("DeerFlow import ready")'], check=True, **flags)


if __name__ == '__main__':
    main()
