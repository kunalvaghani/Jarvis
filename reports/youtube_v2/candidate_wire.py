"""Real built-in stdio contract checks for an UNREGISTERED staged candidate."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
calls = [
    ('initialize', {'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'audit','version':'1'}}),
    ('ping', {}), ('tools/list', {}),
    ('tools/call', {'name':'youtube_queue_add','arguments':{'video':'aqz-KE-bpKQ'}}),
    ('tools/call', {'name':'youtube_queue_list','arguments':{}}),
    ('tools/call', {'name':'youtube_queue_add','arguments':{'video':'aqz-KE-bpKQ','approved':True}}),
    ('tools/call', {'name':'youtube_pause','arguments':{}}),
    ('tools/call', {'name':'youtube_create_playlist','arguments':{'title':'not-created'}}),
]
requests = [dict(jsonrpc='2.0',id=i+1,method=name,params=args) for i,(name,args) in enumerate(calls)]
start = time.perf_counter()
child = subprocess.Popen([sys.executable,str(HERE/'candidate/server.py'),'--runtime','builtin','--allow-write'],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',
    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    stdout, stderr = child.communicate(''.join(json.dumps(r)+'\n' for r in requests), timeout=20)
except subprocess.TimeoutExpired:
    child.kill()
    child.communicate()
    raise
responses = [json.loads(line) for line in stdout.splitlines()]
assert child.returncode == 0 and len(responses)==len(requests), 'Incomplete wire responses'
assert len(responses[2]['result']['tools'])==108
assert responses[3]['result']['isError'] is False
assert responses[4]['result']['structuredContent']['result']['videos']==['aqz-KE-bpKQ']
for index in [5,6,7]:
    assert responses[index]['result']['isError'] is True
assert 'Default profile only' in responses[6]['result']['content'][0]['text']
assert 'trusted Jarvis approval callback required' in responses[7]['result']['content'][0]['text']
assert not stderr, 'Unexpected child diagnostics'
(HERE/'candidate-wire.json').write_text(json.dumps(dict(
    elapsed_ms=round((time.perf_counter()-start)*1000,3), catalog_count=108,
    scope='Real stdio; local queue only; browser/account mutation fail closed; no active registration',
    requests=requests, responses=responses), indent=2), encoding='utf-8')
