"""Owned synthetic workload: durable admission/dispatch cost versus old memory FIFO.

No tool effects, model inference, microphone or account calls. Not a live latency claim.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import queue
import statistics
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis.commands import Command
from jarvis.task_store import TaskStore
from jarvis.task_scheduler import ScheduledQueue


def distribution(samples):
    ordered = sorted(samples)
    return {'samples':len(samples),'p50_ms':statistics.median(samples)*1000,
            'empirical_p95_ms':ordered[min(len(ordered)-1,int(.95*len(ordered)))]*1000,'worst_ms':max(samples)*1000}


def main(output):
    import psutil
    process = psutil.Process()
    rss_before = process.memory_info().rss
    fifo = queue.Queue(128)
    old, admitted, dispatch = [], [], []
    command = Command('open', 'synthetic fixture; never executed')
    for _ in range(200):
        start=time.perf_counter(); fifo.put_nowait((0,command,threading.Event())); old.append(time.perf_counter()-start)
        fifo.get_nowait(); fifo.task_done()
    with tempfile.TemporaryDirectory(prefix='jarvis-queue-benchmark-') as directory:
        store = TaskStore(Path(directory)/'queue.sqlite3')
        scheduler = ScheduledQueue(store, observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'battery_low':False,'desktop':True})
        start_batch = time.perf_counter()
        for _ in range(200):
            start = time.perf_counter()
            identity, _ = store.admit(asdict(command))
            admitted.append(time.perf_counter()-start)
            store.transition(identity,'CLASSIFYING')
            scheduler.put_nowait((0,command,threading.Event()), identity)
            start = time.perf_counter(); scheduler.get(); dispatch.append(time.perf_counter()-start)
            scheduler.outcome('COMPLETED','Synthetic no-effect handler',{'fixture':True}); scheduler.task_done()
        elapsed = time.perf_counter()-start_batch
        counts = scheduler.snapshot()['counts']
        storage_bytes = sum(p.stat().st_size for p in Path(directory).iterdir())
        store.db.close()
    value = {'date':'2026-10-23','scope':'synthetic owned SQLite + fake resources; sequential no-effect handlers',
             'baseline_memory_admission':distribution(old),'durable_admission':distribution(admitted),
             'dispatch_with_200_accumulated_history_rows':distribution(dispatch),
             'wall_seconds':elapsed,'verified_states':counts,'rss_before_mb':rss_before/1048576,
             'rss_after_mb':process.memory_info().rss/1048576,'database_and_wal_bytes_before_close':storage_bytes,
             'note':'Durability adds overhead. Excludes speech/UI/models/tools and cannot establish live throughput or responsiveness.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
