"""Same-journal old/new observation benchmark. No code execution or source writes."""
import csv
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from jarvis.coding_files import FileSession
from tests.test_native_coding import files


def main():
    spec=importlib.util.spec_from_file_location('jarvis._coding_files_before',BASE/'.jarvis-runtime/jarvis-audit/module21-pre/jarvis__coding_files.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    rows=[]
    with tempfile.TemporaryDirectory() as tmp:
        session=files(Path(tmp));journal=session.run/'file-events.jsonl'
        events=[{'stage':stage,'signature':str(i),'path':'fixture.py'} for i in range(500) for stage in ('attempted','applied')]
        journal.write_text(''.join(json.dumps(e)+'\n' for e in events))
        for label,method in [('before',old.FileSession.uncertain),('after',FileSession.uncertain)]:
            for i in range(25):
                tracemalloc.start();start=time.perf_counter_ns();result=method(session);ms=(time.perf_counter_ns()-start)/1e6
                _,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert result is False
                rows.append({'version':label,'mode':'cold' if i<5 else 'warm','sample':i,'ms':ms,'python_peak_bytes':peak})
        with journal.open('a') as h:h.write(json.dumps({'stage':'attempted','signature':'uncertain-last'})+'\n')
        assert old.FileSession.uncertain(session) is FileSession.uncertain(session) is True
    out=BASE/'artifacts/jarvis-audit/modules/21-native-coding'
    with (out/'benchmarks.csv').open('w',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    summary={'equivalent':True,'samples_per_version':25,'journal_rows':1000,'external_effects':0,
      'scope':'Same1000 paired action rows, five first calls/twenty warm calls per method, same imported process and filesystem cache. False for complete journal; True for an appended uncertain action. Imports/construction excluded. No inference/TTFT/audio/GPU or end-to-end build performance claim.'}
    for label in ('before','after'):
        summary[label]={}
        for mode in ('cold','warm'):
            selected=[r for r in rows if r['version']==label and r['mode']==mode];values=sorted(r['ms'] for r in selected)
            summary[label][mode]={'p50_ms':statistics.median(values),'p95_ms':values[math.ceil(.95*len(values))-1],'python_peak_bytes':max(r['python_peak_bytes'] for r in selected)}
    (out/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
