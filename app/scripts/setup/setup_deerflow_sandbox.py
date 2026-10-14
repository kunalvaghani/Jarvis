"""Build the reviewed free offline sandbox; never copies secrets into the image."""
from pathlib import Path
import shutil
from jarvis.repo_acquisition import command
from jarvis.docker_runtime import HOST


def main():
    base = Path(__file__).resolve().parents[2]
    binary = shutil.which('docker')
    if not binary:
        raise ValueError('Install Docker Desktop first.')
    command([binary, '--host', HOST, 'build', '--tag', 'jarvis-deerflow-runtime:1',
             str(base / 'integrations/deerflow/runtime')], timeout=900, limit=2000000)
    print('Reviewed free sandbox image built.')


if __name__ == '__main__':
    main()
