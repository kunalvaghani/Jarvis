"""Read-only Blender executable/version discovery; never installs or starts a project."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis.blender_installation import executables


def discover(explicit=None):
    found=[]
    for path in executables(explicit):
        result=subprocess.run([str(path),'--version'],capture_output=True,text=True,timeout=15,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        found.append({'executable':str(path),'exit_code':result.returncode,'version_output':result.stdout[:2000]})
    return found


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--blender-exe')
    print(json.dumps(discover(parser.parse_args().blender_exe),indent=2))
