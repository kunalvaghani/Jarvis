"""Bounded public-guide census and matched ranking benchmark; never runs helpers."""
import csv
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
from types import SimpleNamespace

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/11-skill-selection'


def main():
    from jarvis.hermes_skills import HermesSkills
    from jarvis.skill_memory import SkillMemory
    from jarvis.obsidian_memory import ObsidianMemory
    from jarvis import utility_profiles,deerflow
    import jarvis.capabilities as after
    OUT.mkdir(parents=True,exist_ok=True)
    catalog=HermesSkills(BASE);assert not catalog.error,catalog.error
    errors=[];verified=0
    for row in catalog.rows:
        try:
            entry=next(f for f in row['files'] if f['path']=='SKILL.md')
            assert catalog.read_bytes(row,'SKILL.md')
            verified+=1
        except Exception as exc:errors.append({'name':row['name'],'error_type':type(exc).__name__})
    # Disabled memory means no personal vault reads or writes.
    native=SkillMemory(ObsidianMemory(BASE,{'enabled':False}))
    census={'date':'2026-10-15 IST','scope':'Read-only checked-out public guide metadata and indexed SKILL.md hash verification; no helpers, personal vault or providers executed.',
      'builtin_guides':len(native.catalog),'hermes_manifest_rows':len(catalog.rows),
      'hermes_guides_verified':verified,'hermes_errors':errors,
      'hermes_resource_entries':sum(len(r['files']) for r in catalog.rows),
      'deerflow_public_guides':len(deerflow.status(BASE)['skills']),
      'utility_environment_present':(BASE/'.venv-skills/Scripts/python.exe').is_file(),
      'utility_availability':utility_profiles.availability(BASE)['status'],'utility_offered':len(utility_profiles.tools(BASE))}
    (OUT/'census.json').write_text(json.dumps(census,indent=2)+'\n',encoding='utf-8')
    assert not errors
    spec=importlib.util.spec_from_file_location('jarvis._skills_before',BASE/'.jarvis-runtime/jarvis-audit/module11-pre/capabilities.py')
    before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
    rows=[{'name':'browser-navigation' if i==0 else f'focus-{i:03}',
           'description':f'Navigate browser website inspect forms document workflow {i}',
           'tools':['browser_inspect','browser_navigate','read_file'],'origin':'Builtins' if i==0 else 'Custom'} for i in range(150)]
    skills=SimpleNamespace(catalog=rows)
    specs={n:SimpleNamespace(name=n,description=n.replace('_',' ')) for n in ('browser_inspect','browser_navigate','browser_fill','browser_click','read_file','open')}
    goal='Navigate browser website inspect form';samples=[];results={};expected=None
    for version,module in [('before',before),('after',after)]:
        for mode,count in [('cold',5),('warm',20)]:
            for index in range(count):
                if mode=='cold' and hasattr(module,'_description_tokens'):module._description_tokens.cache_clear()
                tracemalloc.start();start=time.perf_counter()
                selected=module.rank_tools(specs,goal,skills=skills)
                ms=(time.perf_counter()-start)*1000;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                names=selected
                if expected is None:expected=names
                assert names==expected and names
                samples.append(dict(version=version,mode=mode,index=index,ms=ms,peak_python_bytes=peak,external_side_effects=0))
    for version in ('before','after'):
        for mode in ('cold','warm'):
            sample=[r for r in samples if r['version']==version and r['mode']==mode];values=sorted(r['ms'] for r in sample)
            results[version+'_'+mode]={'samples':len(values),'p50_ms':statistics.median(values),'p95_ms':values[-1 if len(values)==5 else 18],'peak_python_bytes':max(r['peak_python_bytes'] for r in sample)}
    with (OUT/'benchmarks.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(samples[0]));writer.writeheader();writer.writerows(samples)
    summary={'date':'2026-10-15 IST','scope':'Saved pre-change versus current rank_tools, same150 synthetic guide rows/six registered tool labels/machine;5 cleared description-cache and20 warm calls each. Not OS/model cold. No provider/helper/model/GPU work. Tracemalloc transient component allocation, not whole RAM. TTFT/audio/VRAM not applicable.',
             'results':results,'rankings_identical':True,'selected':expected,'external_side_effects':0}
    (OUT/'benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'census':census,'benchmark':summary},indent=2))


if __name__=='__main__':main()
