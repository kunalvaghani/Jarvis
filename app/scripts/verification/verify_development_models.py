"""Real local model probes; no user vault, desktop input or automatic tool replay."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from types import SimpleNamespace
from jarvis.brain import BrainClient
from jarvis.coder import Coder
from jarvis.harness import HarnessClient
from jarvis.agent_context import coding_context
from jarvis.development_tools import DevelopmentTools

BASE=Path(__file__).resolve().parents[2]

def main():
    project=BASE/'artifacts/projects/development-dashboard'
    goal='Create src/Probe.tsx, a React TypeScript component Probe with a button named Add probe and visible text Probe count N. Start at zero, increment on each click. Default export Probe. Only edit this file.'
    client=HarnessClient(BASE,{'planner':'qwen3.5:4b','harness':{'timeout_seconds':180}})
    rows=[]
    try:
        started=time.monotonic()
        plan=client.request('code_plan',lambda:False,goal=goal,project=project.name,development=True,allowed_output_paths=['src/Probe.tsx'],
            files=['package.json','src/App.tsx','src/main.tsx','src/styles.css'],**coding_context(project,goal,'src/Probe.tsx'))
        rows.append({'operation':'harness_development_plan','seconds':round(time.monotonic()-started,3),'result':plan})
        if any(d!='src' for d in plan['directories']) or [s['path'] for s in plan['files']]!=['src/Probe.tsx']:
            raise ValueError('Live planner did not preserve the single explicit probe target; no plan executed.')
    finally:client.close()
    coder=BrainClient(BASE,{'coder':'qwen3.5:4b','planner':'qwen3.5:4b','coding_timeout_seconds':180})
    try:
        started=time.monotonic()
        actions=SimpleNamespace(base=BASE,report=lambda *a:None)
        result=Coder(actions,coder)._run(project,goal,selected=True,plan_override=plan,staged=True)
        rows.append({'operation':'real_qwen_code_generation','model':'qwen3.5:4b','seconds':round(time.monotonic()-started,3),'result':result})
    finally:coder.close()
    tools=DevelopmentTools(BASE)
    try:
        checks=tools.build(project,'vite',lambda:False)
        rows.append({'operation':'real_typecheck_build','exits':[r['exit_code'] for r in checks]})
        if len(checks)!=2 or any(r['exit_code'] for r in checks):raise ValueError('Generated component failed type/build checks.')
    finally:tools.close()
    evidence={'date':datetime.now(timezone.utc).isoformat(),'checks':rows,
        'scope':'Real pinned Harness SDK/local Qwen development planning and local Qwen3.5:4b component generation; actual type/build. Probe component not mounted; UI functionality separately checked in authored dashboard acceptance. No autonomous whole-project model benchmark.'}
    (BASE/'artifacts/reports/development-model-check.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=True),flush=True)

if __name__=='__main__':main()
