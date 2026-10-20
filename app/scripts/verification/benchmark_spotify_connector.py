"""Routing and real local-MCP latency; no Spotify account or playback calls."""
import json
from pathlib import Path
import statistics
import sys
import time
APP=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(APP))
from jarvis.commands import parse
from jarvis.mcp_persistent import PersistentMCP


def summary(values):
    values=sorted(values)
    return {'median_ms':round(statistics.median(values),4),
            'p95_ms':round(values[min(len(values)-1,int(len(values)*.95))],4),'samples':len(values)}


def main():
    phrases=['pause Spotify only','resume my Spotify','jump to 1 minute 35 seconds',
             'make Spotify app 35%','play the fourth item in playlist X','show my Spotify queue']
    routing=[]
    for _ in range(100):
        for text in phrases:
            started=time.perf_counter();parse(text);routing.append((time.perf_counter()-started)*1000)
    server=APP/'integrations/jarvis-connectors/connectors/apps/spotify/server.py'
    config={'enabled':True,'trusted':True,'persistent':True,'command':sys.executable,
            'args':[str(server),'--runtime','builtin','--allow-write'],
            'allow_tools':['spotify_health'],'timeout_seconds':10}
    pool=PersistentMCP(APP)
    try:
        start=time.perf_counter()
        with pool.session(config,lambda:False) as (client,_):client.request('tools/call',{'name':'spotify_health','arguments':{}})
        cold=(time.perf_counter()-start)*1000
        pid=pool.client.process.pid;latencies=[]
        for _ in range(40):
            start=time.perf_counter()
            with pool.session(config,lambda:False) as (client,_):
                assert client.process.pid==pid
                result=client.request('tools/call',{'name':'spotify_health','arguments':{}})
                assert result.get('isError') is False
            latencies.append((time.perf_counter()-start)*1000)
        resources={'status':'NOT MEASURED'}
        try:
            import psutil
            processes=[psutil.Process(pid)];processes+=processes[0].children(recursive=True)
            rss=sum(p.memory_info().rss for p in processes)
            def cpu():return sum(p.cpu_times().user+p.cpu_times().system for p in processes)
            before=cpu();start=time.perf_counter();time.sleep(.5)
            resources={'process_tree_rss_bytes':rss,'idle_cpu_seconds':round(cpu()-before,6),
                       'idle_sample_seconds':round(time.perf_counter()-start,3),'owned_process_count':len(processes)}
        except (ImportError,OSError):pass
        result={'date':'2026-10-20 IST','routing_no_llm':summary(routing),'cold_initialize_health_ms':round(cold,3),
                'warm_mcp_health':summary(latencies),'resources':resources,
                'scope':'Local routing/stdio only; no Spotify API latency, no playback latency guarantee.'}
        path=APP/'artifacts/jarvis-audit/spotify-connector/performance.json'
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result))
    finally:pool.close()


if __name__=='__main__':main()
