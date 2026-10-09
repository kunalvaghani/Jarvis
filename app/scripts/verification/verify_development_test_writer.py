"""Real local test-writer inference and actual authored-dashboard browser checks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from jarvis.brain import BrainClient
from jarvis.development import functional_tests
from jarvis.development_tools import DevelopmentTools

def main():
    base=Path(__file__).resolve().parents[2]
    root=base/'artifacts/projects/development-dashboard'
    client=BrainClient(base,{'planner':'qwen3.5:4b','decision':'qwen3.5:4b','coder':'qwen3.5:4b'})
    tools=DevelopmentTools(base)
    evidence={'date':datetime.now(timezone.utc).isoformat(),
        'scope':'Real local Qwen functional scenario generation and real browser execution on the authored dashboard; no source changes or autonomous project creation.',
        'historical_attempt':'Initial real proposal failed semantic-role validation before execution; contract and bounded inference correction subsequently improved.'}
    try:
        url=tools.start_preview(root,'vite',lambda:False)
        observation=tools.inspect(root,url,[],lambda:False)
        start=time.monotonic()
        tests=functional_tests(client,root,
            'Check working dashboard search, empty state recovery and status filtering; verify outcomes with actual labels from source. Do not test unrelated features.',lambda:False,
            observations=[{'view':v['name'],'snapshot':v['observation']} for v in observation['views'][:2]])
        evidence.update(planning_seconds=round(time.monotonic()-start,3),tests=tests)
        result=tools.inspect(root,url,tests,lambda:False)
        evidence['browser']=result
        evidence['passed']=result['goal_verified']
        print(json.dumps({'model_scenarios':len(tests),'assertions':result['functional_assertions'],'passed':result['goal_verified'],
            'failures':[s for v in result['views'] for s in v['scenarios'] if not s['passed']]}),flush=True)
    except Exception as exc:
        evidence.update(error=str(exc),passed=False)
        raise
    finally:
        client.close()
        tools.close()
        (base/'artifacts/reports/development-test-planner-check.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
