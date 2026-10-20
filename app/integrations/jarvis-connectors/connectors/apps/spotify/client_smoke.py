"""Real Jarvis MCP stdio smoke; no Spotify playback, network or account writes."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[4]))
from jarvis.mcp_bridge import StdioClient

def main():
    config={'enabled':True,'trusted':True,'command':sys.executable,
            'args':[str(HERE/'server.py'),'--runtime','builtin','--allow-write'],
            'allow_tools':['spotify_health'],'timeout_seconds':10}
    client=StdioClient(config,HERE,lambda:False)
    try:
        client.initialize()
        rows=client.tools()
        assert len(rows)==86 and len({r['name'] for r in rows})==86
        result=client.request('tools/call',{'name':'spotify_health','arguments':{}})
        assert result.get('isError') is False
        print('PASS: 86 tools discovered and health invoked over real MCP stdio (builtin protocol runtime).')
    finally:client.close()
if __name__=='__main__':main()
