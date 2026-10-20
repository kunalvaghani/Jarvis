"""Real wire smoke by default; --live-local needs explicit human playback consent."""
import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP))
from jarvis.spotify_host import call
from jarvis.mcp_bridge import StdioClient


def wire():
    server=APP/'integrations/jarvis-connectors/connectors/apps/spotify/server.py'
    config={'enabled':True,'trusted':True,'command':sys.executable,
            'args':[str(server),'--runtime','builtin','--allow-write'],
            'allow_tools':['spotify_health'],'timeout_seconds':10}
    client=StdioClient(config,APP,lambda:False)
    try:
        client.initialize()
        rows=client.tools()
        assert len(rows)==86 and len({row['name'] for row in rows})==86
        result=client.request('tools/call',{'name':'spotify_health','arguments':{}})
        assert result.get('isError') is False
        return {'mode':'real_mcp_stdio','tools':len(rows),'health':'PASS','spotify_account_operations':False}
    finally:client.close()


def live_local(already_open=False):
    """Actual ToolRegistry -> persistent child -> WinRT/Pycaw; never account/library calls."""
    allowed={'open_desktop','local_status','local_play','local_pause','local_next','local_previous',
             'local_seek','local_volume_status','local_volume','local_mute'}
    approved=[]
    def approve(kind, detail, cancelled):
        operation=json.loads(detail)['call']['name'][8:]
        if operation not in allowed or cancelled(): raise ValueError('Outside explicitly consented local smoke scope')
        approved.append(operation)
    actions=SimpleNamespace(base=APP,config={},_approve=approve,last_media=None,report=lambda *args:None)
    results=[]
    def run(operation, **arguments):
        start=time.perf_counter()
        try:
            data=call(actions,operation,arguments,lambda:False)
            results.append({'operation':operation,'status':'response_received',
                            'accepted':data.get('accepted'),'verified':data.get('verified'),
                            'latency_ms':round((time.perf_counter()-start)*1000,2)})
            return data
        except Exception as exc:
            # Privacy: no title, account identity, device ID, URL or exception value is saved.
            results.append({'operation':operation,'status':'BLOCKED','error_type':type(exc).__name__})
            raise
    try:
        if not already_open:
            run('open_desktop')
            time.sleep(2)
        state=run('local_status')
        playing=state.get('playback_status')=='playing'
        first='local_pause' if playing else 'local_play'
        second='local_play' if playing else 'local_pause'
        run(first); time.sleep(.5); run('local_status')
        run(second); time.sleep(.5); run('local_status')
        run('local_next'); time.sleep(.7); run('local_status')
        run('local_previous'); time.sleep(.7); current=run('local_status')
        position=current.get('position_ms')
        if type(position) is int:
            run('local_seek',position_ms=max(0,position+3000))
            run('local_status')
            run('local_seek',position_ms=max(0,position))
        volume=run('local_volume_status')
        levels=volume.get('volume_percent',[]); muted=volume.get('muted',[])
        # Avoid flattening independently configured Spotify sessions during restoration.
        if levels and len(set(levels))==1 and muted and len(set(muted))==1:
            run('local_volume',percent=35)
            run('local_mute',enabled=True)
            run('local_volume',percent=levels[0])
            run('local_mute',enabled=muted[0])
    except Exception:
        pass  # A failed/uncertain write stops the sequence; nothing is replayed.
    finally:
        owner=getattr(actions,'_spotify_mcp',None)
        if owner is not None: owner.close()
    return {'mode':'live_windows_local','human_consent_required':True,'results':results,
            'all_planned_operations_completed':len(results)>=15 and not any(r['status']=='BLOCKED' for r in results),
            'account_and_library_operations':'NOT TESTED','approvals':approved}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-local',action='store_true')
    parser.add_argument('--already-open',action='store_true',help='Observe the existing session without reopening Spotify.')
    args=parser.parse_args()
    result=live_local(args.already_open) if args.live_local else wire()
    destination=APP/'artifacts/jarvis-audit/spotify-connector'/('live-local.json' if args.live_local else 'wire-smoke.json')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
