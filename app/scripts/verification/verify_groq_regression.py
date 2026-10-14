"""Selected regression runner: real Groq stays off even on configured machines."""
from datetime import datetime,timedelta,timezone
import os
from pathlib import Path
import sys
import time
import unittest
import json

MODULES=('groq','model_selection','knowledge','question_speed','gpu_scheduler','model_recovery',
    'fast_conversation','conversation_context','docker_sandbox','deerflow','recovery','task_recovery',
    'launcher_readiness','diagnostics','agent_runtime','capabilities','task_graph','task_state',
    'native_tools','step_planning','harness','toolkits','windows_commands','intent_testbook',
    'command_cleanup','tools','brain','inference_limits','ollama_models')


def main():
    base=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(base))
    from jarvis.cloud_policy import DEFAULTS
    for field in DEFAULTS:os.environ.pop('GROQ_'+field.upper(),None)
    os.environ.update(GROQ_ENABLED='false',GROQ_LIVE_TESTS_ENABLED='false')
    sys.path.insert(0,str(base/'tests'))
    started=time.perf_counter()
    suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_'+name for name in MODULES])
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    report={'date':datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime('%Y-%m-%d IST'),
        'offline_regression':{'tests':result.testsRun,'passed':result.wasSuccessful(),'seconds':round(time.perf_counter()-started,3),
            'skipped':len(result.skipped),'failure_ids':[case.id() for case,_ in result.failures+result.errors],'modules':list(MODULES)},
        'groq_live_inference_calls':0,'groq_live_tests_enabled':False,
        'scope':'Explicit offline/mocked modules and loopback fake provider. Cloud disabled in this runner regardless of configured account.',
        'routing_report':'groq-routing-verification.json','local_model_inventory':'groq-local-model-inventory.json',
        'unverified':['real Groq entitlement/billing','real Groq answer quality or latency','full GUI/microphone startup','live local model switching latency']}
    (base/'artifacts/reports/groq-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
