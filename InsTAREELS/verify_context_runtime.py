"""Actual background selector transport with authored sessions; no task actions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import time
import sys
from jarvis.knowledge import Knowledge


def main():
    base=Path(__file__).resolve().parent
    output=base/'artifacts/context-runtime-check.json'
    result={'date':datetime.now(timezone.utc).isoformat(),
        'scope':'Actual local selector, authored temporary sessions, nonblocking planner consumption; no desktop actions or simultaneous-model throughput claim.'}
    if '--warm' in sys.argv:
        import requests
        client=requests.Session();client.trust_env=False
        started=time.monotonic()
        try:
            response=client.post('http://127.0.0.1:11434/api/chat',json={'model':'qwen3.5:0.8b','messages':[],
                'stream':False,'keep_alive':'5m','options':{'num_gpu':0,'num_ctx':2048,'num_thread':4}},timeout=(1,20))
            response.raise_for_status()
            result['fixture_model_preload_seconds']=round(time.monotonic()-started,3)
            result['scope']+=' Selector latency excludes this explicit fixture preload; production cold requests may use manual choices.'
        finally:client.close()
    events=[]
    with tempfile.TemporaryDirectory(prefix='context-runtime-',dir=base/'.jarvis-runtime') as temporary:
        worker=Knowledge({},lambda *args:events.append(args))
        worker.attach_conversations(Path(temporary)/'conversations.sqlite3',{'enabled':True})
        worker.attach_selector({'enabled':True,'model':'qwen3.5:0.8b','timeout_seconds':3})
        calls=[]
        request=worker.context_selector.request
        def tracked(*args):
            calls.append(threading.current_thread().name)
            return request(*args)
        worker.context_selector.request=tracked
        try:
            for question,answer in (
                ('Python calculator app code','Tkinter buttons for addition and multiplication'),
                ('Python snake game app code','Board dice rules and player movement')):
                session=worker.conversations.start_session()
                turn=worker.conversations.begin(session,question)
                worker.conversations.finish(turn,answer)
            worker.app_snapshot_provider=lambda:{'current':{'handle':42,'pid':100,'title':'Python calculator fixture','status':'open'}}
            goal='Improve multiplication in that app'
            result['original_request']=goal
            result['app_context_scope']='Authored open calculator metadata; actual window lifecycle tested separately.'
            started=time.monotonic()
            future=worker.prepare_context(goal)
            call_started=time.monotonic()
            initial=worker.planning_context(goal)
            result['planner_initial_call_seconds']=round(time.monotonic()-call_started,6)
            result['initial_ready']=initial is not None
            prepared=future.result(timeout=5)
            result.update(selector_seconds=round(time.monotonic()-started,3),
                model=worker.context_selector.options['model'],threads=calls,events=events,
                selected_source=prepared['source'] if prepared else None,
                remaining_choices=len(prepared['matches']) if prepared else None,
                ready_context=worker.planning_context(goal))
            result['passed']=bool(calls==['Jarvis context selector'] and prepared and
                prepared['source']=='saved_memory' and not prepared['matches'] and
                'multiplication' in json.dumps(result['ready_context']) and
                result['planner_initial_call_seconds']<.1)
        finally:
            worker.close()
            output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__': main()
