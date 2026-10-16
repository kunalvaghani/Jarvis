"""Build the isolated runtime for generated MCP adapters (jarvis-mcp-runtime:1).

FROM the reviewed jarvis-repository-runtime:1 (Python 3.13, label
org.jarvis.repository-runtime=1) plus the official MCP Python SDK pinned to
2.3.0. Network is used only by this build; generated servers run with
--network none. Writes the installed package list for review.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parents[2]
IMAGE = 'jarvis-mcp-runtime:1'
SDK = 'mcp==2.3.0'
HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'
DOCKERFILE = f"""FROM jarvis-repository-runtime:1
USER root
RUN python -m pip install --no-cache-dir --disable-pip-version-check {SDK} && python -m pip freeze > /opt/mcp-freeze.txt
USER 65534:65534
LABEL org.jarvis.mcp-runtime="1" org.jarvis.mcp-sdk="{SDK}"
"""


def main():
    docker = shutil.which('docker')
    if not docker:
        raise SystemExit('Docker CLI unavailable.')
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / 'Dockerfile').write_text(DOCKERFILE, encoding='utf-8')
        subprocess.run([docker, '--host', HOST, 'build', '--pull=false', '-t', IMAGE, folder], check=True, timeout=900)
    freeze = subprocess.run([docker, '--host', HOST, 'run', '--rm', '--network', 'none', '--entrypoint', 'cat', IMAGE,
                             '/opt/mcp-freeze.txt'], check=True, capture_output=True, text=True, timeout=120).stdout
    image = json.loads(subprocess.run([docker, '--host', HOST, 'image', 'inspect', IMAGE], check=True,
                                      capture_output=True, text=True, timeout=60).stdout)[0]
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / '.jarvis-runtime' / 'mcp-runtime.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'image': IMAGE, 'image_id': image['Id'], 'sdk': SDK,
                               'packages': sorted(freeze.split())}, indent=1) + '\n', encoding='utf-8')
    print(image['Id'], SDK, len(freeze.split()), 'packages')


if __name__ == '__main__':
    main()
