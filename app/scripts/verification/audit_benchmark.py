"""Comparable bounded fixtures; no live model/account calls or personal content."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import tempfile
import time
from types import SimpleNamespace
from jarvis.cognition import Cognition
from jarvis.commands import Command, parse
from jarvis.experience import hotness_many
from jarvis.tools import ToolRegistry
from tests.intent_permutations import scenarios

BASE=Path(__file__).resolve().parents[2]

def summary(values):
    return {'n':len(values),'p50':statistics.median(values),'p95':sorted(values)[int((len(values)-1)*.95)],'max':max(values)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('before','after'),required=True)
    phase=parser.parse_args().phase
    expected=json.loads((BASE/'tests/fixtures/intent_testbook_expected.json').read_text())
    rows=scenarios(); counts=Counter(); confusion=Counter(); latencies=[]
    started=time.perf_counter()
    for number,*texts in rows:
        for text in texts:
            at=time.perf_counter()
            try: actual=parse(text).kind
            except ValueError: actual='unparsed'
            latencies.append((time.perf_counter()-at)*1000)
            counts['total']+=1;counts['correct']+=actual==expected[number]
            confusion[(expected[number],actual)]+=1
    labels=sorted({a for a,b in confusion}|{b for a,b in confusion})
    metrics={}
    for label in labels:
        tp=confusion[label,label];pred=sum(v for (a,b),v in confusion.items() if b==label);gold=sum(v for (a,b),v in confusion.items() if a==label)
        metrics[label]={'precision':tp/pred if pred else 0,'recall':tp/gold if gold else 0}
    result={'date':'2026-10-14 IST','phase':phase,'scope':'Authored 800 scenario/2400 phrasing oracle and bounded synthetic sensor fixtures; no real LLM answer quality or end-user acceptance measurement',
        'intent':{'correct':counts['correct'],'total':counts['total'],'accuracy':counts['correct']/counts['total'],
            'per_class':metrics,'routing_ms':summary(latencies),'total_seconds':time.perf_counter()-started},'cold_parser_ms':latencies[0]}
    with tempfile.TemporaryDirectory() as folder:
        a=SimpleNamespace(base=Path(folder),current_item=None,whatsapp_prompts=[],pending_tasks=[],session_style={},approvals_waiting=0,memory=None,config={},allowed_tools={'open','application_inspect'})
        mind=Cognition(a);ticks=[];ingress=[];samples=[]
        original=mind.tick
        def tick():
            samples.append(time.monotonic());at=time.perf_counter();original();ticks.append((time.perf_counter()-at)*1000)
        mind.tick=tick;mind.write_state=lambda:time.sleep(.18)
        mind.start()
        start=time.monotonic()
        try:
            while time.monotonic()-start<6:
                at=time.perf_counter()
                for i in range(20):mind.perceive('sensor','sensor',f'Fixture {i}',.7)
                mind.perceive('you','speech','Synthetic voice',1)
                ingress.append((time.perf_counter()-at)*1000);time.sleep(.025)
        finally:mind.close()
        result['tick_ms']=summary(ticks);result['ingress_21_ms']=summary(ingress)
        result['interval_ms']=summary([(b-a)*1000 for a,b in zip(samples,samples[1:])])
        result['stop_workers_alive']=any(t.is_alive() for t in (mind.thread,mind.writer_thread))
        # Admission fairness has an independent expected value, not self-reported success.
        mind=Cognition(a)
        for i in range(200):
            mind.perceive('you','speech',f'Old {i}',1);mind.percepts[-1].at=time.time()-3600
        mind.perceive_window('Fresh owned fixture');mind.tick()
        result['fresh_window_rank1']=mind.attention[0].content=='Fresh owned fixture'
        # Exact scoped catalog/unsupported execution contracts, no UI effects.
        registry=ToolRegistry(a)
        result['scoped_tools']=sorted(row['action'] for row in registry.catalog())
        decay=[time.time()-i*86400 for i in range(2000)];values=[]
        hotness_many(decay,now=decay[0])
        for _ in range(30):
            at=time.perf_counter();hotness_many(decay,now=decay[0]);values.append((time.perf_counter()-at)*1000)
        result['decay_2000_ms']=summary(values)
    path=BASE/'artifacts/jarvis-audit'/('benchmark-'+phase+'.json')
    if path.exists():raise ValueError('Preserve earlier measurements')
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='intent'},indent=2));print('Intent',counts['correct'],'/',counts['total'])

if __name__=='__main__':main()
