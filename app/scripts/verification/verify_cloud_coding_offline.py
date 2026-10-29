"""Run provider/controller regressions with remote networking denied, never inference."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import requests

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))


def main():
    denied=[];loopback=0;original=requests.sessions.Session.request;original_connect=socket.socket.connect
    def request(client,method,url,**kwargs):
        nonlocal loopback
        target=urlsplit(url)
        if target.hostname not in ('127.0.0.1','localhost','::1') or target.port==11434:
            denied.append({'surface':'http','host':target.hostname,'method':method})
            raise AssertionError('REMOTE_INFERENCE_NETWORK_DENIED')
        loopback+=1
        return original(client,method,url,**kwargs)
    def connect(sock,address):
        if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1'):
            denied.append({'surface':'socket'})
            raise AssertionError('REMOTE_INFERENCE_SOCKET_DENIED')
        return original_connect(sock,address)
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'tests.test_required_observations','tests.test_cloud_coding_quota','tests.test_cloud_coding_routes','tests.test_groq','tests.test_model_selection'])
    started=time.monotonic()
    with patch.object(requests.sessions.Session,'request',request),patch.object(socket.socket,'connect',connect):
        result=unittest.TextTestRunner(verbosity=1).run(suite)
    files=['jarvis/cloud_quota.py','jarvis/coding_cloud_policy.py','jarvis/coding_cloud_context.py','jarvis/coding_cloud_routes.py',
           'jarvis/gemini_adapter.py','jarvis/groq_adapter.py','jarvis/hybrid_inference.py','jarvis/native_coding.py','jarvis/codex_workload.py',
           'tests/test_required_observations.py','tests/test_cloud_coding_quota.py','tests/test_cloud_coding_routes.py','scripts/verification/verify_cloud_coding_offline.py']
    files+=['jarvis/execution_contract.py','jarvis/callback_contract.py','jarvis/coding_files.py','jarvis/structured_output.py','jarvis/cloud_cli.py',
            'jarvis/config_contract.py','jarvis/model_performance.py','jarvis/model_selection.py','scripts/verification/verify_autonomous_repair.py']
    value={'date':datetime.now(timezone.utc).isoformat(),'status':'PASS' if result.wasSuccessful() else 'FAIL',
        'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'seconds':round(time.monotonic()-started,3),'real_gemini_inference_requests':0,'real_groq_inference_requests':0,
        'real_cloud_inference_tokens':0,'paid_api_usage':0,'network_guard':'External HTTP and socket connections refused;owned loopback fake providers only. Live Ollama11434 also refused.',
        'loopback_test_http_requests':loopback,'external_attempts_denied':denied,'application_acceptance':False,
        'source_sha256':{name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in files},
        'scope':'Actual controller/quota/adapter regressions with provider-shaped doubles. Not real provider quality or generated-application acceptance.'}
    target=BASE/'artifacts/autonomous-repair/cloud-coding-zero-token.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value[key] for key in ('status','tests','seconds','real_cloud_inference_tokens','application_acceptance')}))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
