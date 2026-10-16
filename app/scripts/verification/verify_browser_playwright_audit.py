"""Matched real headless-browser summary benchmark, never uses a user profile."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/14-browser-playwright'


def main():
    import jarvis.browser_worker as after
    from playwright.sync_api import sync_playwright
    spec=importlib.util.spec_from_file_location('jarvis._browser_before',BASE/'.jarvis-runtime/jarvis-audit/module14-pre/jarvis__browser_worker.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    chrome=next(p for p in (Path('C:/Program Files/Google/Chrome/Application/chrome.exe'),Path('C:/Program Files (x86)/Google/Chrome/Application/chrome.exe')) if p.is_file())
    html='<title>Owned synthetic benchmark</title>'+''.join(f'<button aria-label="Action {i}">Action {i}</button>' for i in range(80))+'<video></video>'
    samples=[];results={};expected=None
    class Locator:
        def __init__(self,value,calls):self.value,self.calls=value,calls
        @property
        def first(self):return Locator(self.value.first,self.calls)
        def count(self):self.calls.append('count');return self.value.count()
        def evaluate(self,*a):self.calls.append('evaluate');return self.value.evaluate(*a)
        def evaluate_all(self,*a):self.calls.append('evaluate_all');return self.value.evaluate_all(*a)
    class Page:
        def __init__(self,value,calls):self.value,self.calls=value,calls
        @property
        def url(self):return self.value.url
        def locator(self,*a):return Locator(self.value.locator(*a),self.calls)
        def title(self):self.calls.append('title');return self.value.title()
        def evaluate(self,*a):self.calls.append('evaluate');return self.value.evaluate(*a)
    with sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True,executable_path=str(chrome))
        try:
            for version,module in [('before',before),('after',after)]:
                for mode,count in [('cold',5),('warm',20)]:
                    context=None
                    try:
                        for index in range(count):
                            if context is None or mode=='cold':
                                if context:context.close()
                                context=browser.new_context();context.route('**/*',lambda r:r.abort());page=context.new_page();page.set_content(html)
                            calls=[];session=module.Session();session.page=Page(page,calls);session.context=context
                            tracemalloc.start();start=time.perf_counter();report=session.inspect()
                            ms=(time.perf_counter()-start)*1000;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                            controls=[{k:row.get(k) for k in ('name','role','href')} for row in report['controls']]
                            if expected is None:expected=controls
                            assert controls==expected and len(controls)==80
                            assert len(calls)==(4 if version=='before' else 1)
                            samples.append(dict(version=version,mode=mode,index=index,ms=ms,peak_python_bytes=peak,browser_round_trips=len(calls),real_external_effects=0))
                    finally:
                        if context:context.close()
        finally:browser.close()
    for version in ('before','after'):
        for mode in ('cold','warm'):
            rows=[r for r in samples if r['version']==version and r['mode']==mode];values=sorted(r['ms'] for r in rows)
            results[version+'_'+mode]=dict(samples=len(values),p50_ms=statistics.median(values),p95_ms=values[-1 if len(values)==5 else 18],peak_python_bytes=max(r['peak_python_bytes'] for r in rows))
    with (OUT/'benchmarks.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    summary=dict(date='2026-10-15 IST',results=results,controls_identical=True,scope='Installed Chrome/Playwright1.63.0, one headless owned browser;5 first summaries of fresh isolated contexts,20 repeated warm summaries per algorithm. Page loaded before timer. Same80 explicit-ARIA buttons/video fixture and machine; before4 browser round trips,after1. Tracemalloc Python component allocation only, not Chrome/whole RAM. All external requests aborted, no user profile or persistent download. No GPU/model/voice; TTFT/audio/VRAM not applicable.')
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
