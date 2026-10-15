"""Controlled tick and decay benchmark; owned fixtures and injected storage delay."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import time
from types import SimpleNamespace
from jarvis.cognition import Cognition
from jarvis.commands import parse
from jarvis.experience import hotness

BASE = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('baseline','upgraded'), required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        actions = SimpleNamespace(base=Path(folder),current_item=None,whatsapp_prompts=[],pending_tasks=[],session_style={},approvals_waiting=0)
        mind = Cognition(actions)
        intervals, timings, last = [], [], []
        tick = mind.tick
        def measure():
            now = time.perf_counter()
            if last: intervals.append((now-last[-1])*1000)
            last.append(now)
            tick()
            timings.append((time.perf_counter()-now)*1000)
        mind.tick = measure
        mind.write_state = lambda:time.sleep(.18)
        mind.start()
        started=time.monotonic()
        while time.monotonic()-started<3.2:
            for i in range(20): mind.perceive(('screen','gods_eye','weather','whatsapp')[i%4],'sensor','Synthetic event',.7)
            mind.perceive('you','speech','Synthetic voice',.9)
            time.sleep(.025)
        mind.close()
        mind.thread.join(timeout=2)
        routing=[]
        for _ in range(100):
            for command in ('pause','volume up','open Chrome'):
                start=time.perf_counter();parse(command);routing.append((time.perf_counter()-start)*1000)
        stamps=[time.time()-i*86400 for i in range(2000)]
        start=time.perf_counter()
        for _ in range(20): [hotness(t,now=stamps[0]) for t in stamps]
        scalar=(time.perf_counter()-start)*1000/20
        vector=None
        if args.mode=='upgraded':
            from jarvis.experience import hotness_many
            hotness_many(stamps,now=stamps[0])
            start=time.perf_counter()
            for _ in range(20):hotness_many(stamps,now=stamps[0])
            vector=(time.perf_counter()-start)*1000/20
        def summary(rows):
            return {'samples':len(rows),'median':statistics.median(rows),'p95':sorted(rows)[int(.95*(len(rows)-1))],'max':max(rows)}
        result={'date':'2026-10-14 IST','mode':args.mode,'scope':'Synthetic sensor bursts, 4 Hz loop with 180 ms injected storage delay, 300 parser calls including first resolver import, 2000 timestamp decay batch. Not production/OS real-time certification.',
            'tick_ms':summary(timings),'interval_ms':summary(intervals),'routing_ms':summary(routing),
            'scalar_decay_ms':scalar,'batch_decay_ms':vector,
            'source_sha256':{name:hashlib.sha256((BASE/'jarvis'/name).read_bytes()).hexdigest() for name in ('cognition.py','context_hub.py','engine.py','commands.py','deliberation.py','task_recovery.py','experience.py')}}
        path=BASE/'artifacts/reports'/f'cognition-{args.mode}.json'
        if path.exists(): raise ValueError('Preserve prior measurements before rerunning.')
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()
