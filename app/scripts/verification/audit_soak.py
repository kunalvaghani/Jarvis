"""Bounded 30-second offline cognition soak with five ingress producers."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import psutil
from jarvis.cognition import Cognition

BASE=Path(__file__).resolve().parents[2]

def main():
    process=psutil.Process();before=process.memory_info().rss
    with tempfile.TemporaryDirectory() as folder:
        mind=Cognition(SimpleNamespace(base=Path(folder),current_item=None,whatsapp_prompts=[],pending_tasks=[],session_style={},approvals_waiting=0,memory=None))
        mind.start();peak=before;samples=[]
        def producer(i):
            for j in range(20):mind.perceive('sensor','sensor',f'Owned fixture {i}:{j}',.5)
        started=time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=5) as pool:
                for iteration in range(120):
                    list(pool.map(producer,range(5)))
                    mind.perceive('you','speech',f'Voice {iteration}',1.)
                    assert len(mind.percepts)<=200 and len(mind.inbox)<=200
                    assert mind.thread.is_alive()
                    peak=max(peak,process.memory_info().rss)
                    samples.append(mind.cycles);time.sleep(.25)
            assert mind.cycles>=100
            assert mind.persistence_healthy()
        finally:mind.close()
        assert not mind.thread.is_alive() and not mind.writer_thread.is_alive()
        result={'date':'2026-10-14 IST','passed':True,'scope':'30-second owned synthetic cognition soak; no external actions or model loads',
            'seconds':time.monotonic()-started,'iterations':120,'producers':5,'events':12120,'cycles':mind.cycles,
            'rss_before_bytes':before,'rss_peak_bytes':peak,'rss_after_bytes':process.memory_info().rss,
            'workers_alive_after_stop':False}
    (BASE/'artifacts/jarvis-audit/soak.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
