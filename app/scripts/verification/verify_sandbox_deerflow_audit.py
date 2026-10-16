"""Compare exact sandbox inventories on isolated synthetic trees; no Docker/model run."""
import csv
import importlib.util
from importlib import metadata
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/28-sandbox-deerflow';PRE=BASE/'.jarvis-runtime/jarvis-audit/module28-pre'


def main():
    from jarvis.deerflow_sandbox import SandboxJob
    spec=importlib.util.spec_from_file_location('jarvis._sandbox_before',PRE/'jarvis__deerflow_sandbox.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-inventory-') as folder:
        job=SandboxJob(folder)
        for i in range(100):
            root=job.root/'workspace'/f'd{i:03}';root.mkdir(parents=True)
            for j in range(30):(root/f'f{j:03}.txt').write_text('fixture')
        (job.root/'outputs').mkdir()
        expected=before.SandboxJob.inventory(job);assert job.inventory()==expected
        for sample in range(25):
            for version,call in (('before',lambda:before.SandboxJob.inventory(job)),('after',job.inventory)):
                tracemalloc.start();start=time.perf_counter_ns();result=call()
                elapsed=(time.perf_counter_ns()-start)/1e6;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                assert result==expected
                rows.append(dict(version=version,sample=sample,phase='initial' if sample<5 else 'warm',milliseconds=elapsed,
                    peak_python_bytes=peak,docker_calls=0,network_calls=0))
    with (OUT/'benchmarks.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={}
    for version in ('before','after'):
        warm=[r for r in rows if r['version']==version and r['phase']=='warm'];values=sorted(r['milliseconds'] for r in warm)
        summary[version]=dict(p50_ms=statistics.median(values),p95_ms=values[18],peak_python_bytes=max(r['peak_python_bytes'] for r in warm))
    summary.update(equivalent=True,real_external_actions=0,fixture_files=3000,inventory_rows=len(expected),scope='Identical first200 lexical inventory rows;20 warm+5 initial per version. Not cold processes, container/render/model/network/RSS/VRAM.')
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2))
    import psutil
    env=dict(date='2026-10-16 IST',python=sys.version,platform=platform.platform(),ram_bytes=psutil.virtual_memory().total,
        packages={p:metadata.version(p) for p in ('requests','pytest','psutil','Pillow')},deerflow_revision='a5e71751d7a9f8f4a71ca458da3984fc1284d098')
    (OUT/'environment.json').write_text(json.dumps(env,indent=2))
    print(json.dumps(summary))


if __name__=='__main__':main()
