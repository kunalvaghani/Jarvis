"""Register the local Blender child without installing dependencies or launching Blender."""
import argparse
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[2]


def register(base=BASE, python=None, bridge_config=None, disable=False):
    base=Path(base).resolve(strict=True)
    server=base/'integrations/jarvis-connectors/connectors/apps/blender/server.py'
    path=base/'.jarvis/mcp.json'
    data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'servers':{}}
    if set(data)!={'servers'} or not isinstance(data['servers'],dict):
        raise ValueError('Existing MCP configuration is invalid; preserve it before repair.')
    if path.exists():
        backup=base/'.jarvis-runtime/backups'/('mcp-before-blender-'+str(time.time_ns())+'.json')
        backup.parent.mkdir(parents=True,exist_ok=True)
        backup.write_bytes(path.read_bytes())
    if disable:
        if 'blender' in data['servers']: data['servers']['blender']['enabled']=False
    else:
        config=Path(bridge_config or base/'.jarvis-runtime/blender/default.json').resolve()
        rows=json.loads((server.parent/'catalog.json').read_text())
        data['servers']['blender']={'enabled':True,'trusted':True,'persistent':True,'approval_binding':'blender-v1',
            'command':str(Path(python or sys.executable).resolve(strict=True)),
            'args':[str(server),'--runtime','builtin','--allow-write','--bridge-config',str(config)],
            'allow_tools':[r['tool'] for r in rows],'env_names':[],'timeout_seconds':20}
    temporary=path.with_suffix('.blender-tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
    return data['servers'].get('blender',{})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python')
    parser.add_argument('--bridge-config')
    parser.add_argument('--disable',action='store_true')
    options=parser.parse_args()
    register(python=options.python,bridge_config=options.bridge_config,disable=options.disable)
    print('Blender registration updated. Start/attach its explicitly scoped bridge separately.')
