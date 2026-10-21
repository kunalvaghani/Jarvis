"""Real stdio discovery client; default mode lists schemas and never edits Blender."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[4]))
from jarvis.mcp_bridge import StdioClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge-config',default=str(HERE.parents[4]/'.jarvis-runtime/blender/unconfigured.json'))
    parser.add_argument('--live-health',action='store_true')
    options=parser.parse_args()
    inventory=json.loads((HERE/'catalog.json').read_text())
    config={'enabled':True,'trusted':True,'approval_binding':'blender-v1','command':sys.executable,
        'args':[str(HERE/'server.py'),'--runtime','builtin','--allow-write','--bridge-config',str(Path(options.bridge_config).resolve())],
        'allow_tools':[r['tool'] for r in inventory],'timeout_seconds':15}
    client=StdioClient(config,HERE,lambda:False)
    try:
        client.initialize();rows=client.tools()
        assert len(rows)==203
        assert {r['name'] for r in rows}==set(config['allow_tools'])
        report={'runtime':'Jarvis builtin MCP 2025-11-25, real stdio','count':len(rows),'names':[r['name'] for r in rows]}
        if options.live_health:report['live_health']=client.request('tools/call',{'name':'blender_bridge_health','arguments':{}})
        print(json.dumps(report,indent=2))
    finally:client.close()


if __name__=='__main__':main()
