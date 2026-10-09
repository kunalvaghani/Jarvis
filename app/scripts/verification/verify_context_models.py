"""Compare local context selectors using authored candidates, never private memory."""
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
import requests
from jarvis.context_selector import select_payload
from jarvis.context_selector import settings
from jarvis.conversation_memory import terms

CANDIDATES = [
    {'id':'a','question':'C++ snake and ladder game app code', 'answer':'Win32 board UI, dice rolling and player movement', 'keywords':['game','cpp','snake','ladder']},
    {'id':'b','question':'Python calculator app code', 'answer':'Tkinter buttons for addition, subtraction, multiplication and division', 'keywords':['python','calculator']},
    {'id':'c','question':'Spotify music controls app', 'answer':'Playlist songs, album artwork and playback buttons', 'keywords':['spotify','music']},
]
CASES = [('Continue the C++ snake ladder game','a'), ('Make the Python calculator buttons larger','b'),
         ('Show playlist song artwork on Spotify','c'), ('Improve the app','ambiguous'),
         ('What did we discuss about code?','ambiguous'), ('Explain photosynthesis','none'),
         ('Change the Win32 board dice rules','a'), ('Fix multiplication in the calculator','b')]

if __name__ == '__main__':
    results=[]
    with requests.Session() as client:
        client.trust_env=False
        for model in ('qwen2.5:0.5b','qwen3.5:0.8b','qwen2.5:3b-instruct'):
            rows=[]
            for goal,expected in CASES:
                payload=select_payload(goal,CANDIDATES,settings({'model':model}))
                payload['stream']=False
                started=time.monotonic()
                try:
                    response=client.post('http://127.0.0.1:11434/api/chat',json=payload,timeout=(1,60))
                    response.raise_for_status()
                    data=response.json()
                    chosen=json.loads(data['message']['content'])['id']
                    scores={row['id']:len(terms(goal)&terms(row['question']+' '+row['answer'])) for row in CANDIDATES}
                    values=sorted(scores.values(),reverse=True)
                    guarded='none' if values[0]==0 else 'ambiguous' if values[0]<2 or values[0]==values[1] else chosen if scores.get(chosen,0)==values[0] else 'ambiguous'
                    rows.append({'request':goal,'expected':expected,'chosen':chosen,'correct':chosen==expected,
                                 'guarded':guarded,'guarded_correct':guarded==expected,
                                 'seconds':round(time.monotonic()-started,4),'load_seconds':round(data.get('load_duration',0)/1e9,4)})
                except Exception as exc:
                    rows.append({'request':goal,'expected':expected,'correct':False,'error':type(exc).__name__,
                                 'seconds':round(time.monotonic()-started,4)})
                print(model,len(rows),rows[-1]['seconds'],rows[-1]['correct'],flush=True)
            results.append({'model':model,'correct':sum(row['correct'] for row in rows),'total':len(rows),
                            'guarded_correct':sum(row.get('guarded_correct',False) for row in rows),
                            'warm_median_seconds':round(statistics.median(row['seconds'] for row in rows[1:]),4),'cases':rows})
    record={'date':datetime.now(timezone.utc).isoformat(),'scope':'Authored text context classification; no private memory, microphone or task execution; nonstream harness with production prompt/schema/options; no proof of full task speed improvement', 'results':results}
    Path('artifacts/reports/context-model-check.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps([{key:value for key,value in result.items() if key!='cases'} for result in results],indent=2))
