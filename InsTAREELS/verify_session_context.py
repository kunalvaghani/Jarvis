"""Authored UI selection fixture plus optional actual local answer; no desktop actions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from unittest.mock import Mock

from jarvis.actions import Actions
from jarvis.interface import build_interface
from jarvis.knowledge import Knowledge
from jarvis.ui_preview import export_preview


def wait_for(worker, test, root=None, deadline=90):
    started=time.monotonic()
    while not test() and time.monotonic()-started<deadline:
        if root: root.update()
        time.sleep(.02)
    if not test(): raise RuntimeError('Fixture did not complete: '+str(worker.pending_memory is not None))


def main():
    base=Path(__file__).resolve().parent
    output=base/'artifacts'
    events=[]
    root=tk.Tk(); root.withdraw()
    with tempfile.TemporaryDirectory(prefix='session-context-',dir=base/'.jarvis-runtime') as temporary:
        worker=Knowledge({'model':'qwen3.5:9b','stream':True,'num_gpu':0,'internet':False,
                          'timeout_seconds':60,'max_answer_seconds':120,'num_predict':300,'answer_language':'en'},
                         lambda *args:events.append(args))
        worker.attach_conversations(Path(temporary)/'conversations.sqlite3',{'enabled':True})
        app=Mock(); app.root=root
        app.config={'whisper':{'model':'fixture'},'knowledge':{},'_ui_verification':True,'ui':{'reduced_motion':True}}
        app.speech.options={'enabled':False}
        actions=Actions.__new__(Actions)
        actions.knowledge=worker; actions.task_active=True; actions.task_state=None; actions.report=Mock()
        actions.root=Path('D:/Example/JarvisFiles')
        actions.submit=lambda command:Actions.submit(actions,command)
        app.actions=actions
        app.show_panel=lambda:app.island.expand(True)
        build_interface(app)
        result={'date':datetime.now(timezone.utc).isoformat(),'scope':'Authored off-screen native island events, temporary paired sessions and two actual local model answers. No private memory, microphone or external task execution.', 'requests':[]}
        request_answer=worker.client.request
        def capture_request(request,cancelled):
            result['sent_context']={key:request.get(key) for key in ('history','conversation_context','context_source')}
            result['requests'].append(result['sent_context'])
            return request_answer(request,cancelled)
        worker.client.request=capture_request
        try:
            store=worker.conversations
            for topic,answer in (('Nimbus calculator colors','We chose purple buttons for Nimbus calculator.'),
                                 ('Nimbus snake game colors','We chose blue buttons for Nimbus snake game.')):
                session=store.start_session(); turn=store.begin(session,topic); store.finish(turn,answer)
            worker.quick.answer=Mock(return_value=None)
            worker.start()
            original='What button color did we choose for Nimbus?'
            worker.submit(original)
            wait_for(worker,lambda:worker.pending_memory is not None)
            card=worker.choice_snapshot()
            app.question.set(card['question'])
            app.desk.update_choices(card)
            app.panel.geometry('650x660+20000+20000'); app.panel.deiconify()
            root.update()
            export_preview(app,output/'session-memory-choices-preview.png')
            index=next(i for i,row in enumerate(worker.pending_memory['matches']) if 'calculator' in row['question'])
            button=app.desk.choice_buttons[index]
            button.event_generate('<Enter>',x=10,y=10)
            button.event_generate('<ButtonPress-1>',x=10,y=10)
            button.event_generate('<ButtonRelease-1>',x=10,y=10)
            root.update()
            started=time.monotonic()
            wait_for(worker,lambda:any(kind in {'answer','answer_error'} for kind,_ in events),root)
            answers=[value for kind,value in events if kind=='answer']
            if not answers:
                raise RuntimeError(str([value for kind,value in events if kind=='answer_error']))
            answer=answers[-1]
            result.update(answer=answer,passed=False)
            if 'purple' not in answer.casefold() or 'blue' in answer.casefold():
                raise AssertionError('Answer did not follow the selected memory: '+answer)
            persisted=store.turns(worker.session_id)
            result.update(passed=True,original_question=original,selected_topic='Nimbus calculator colors',
                          answer=answer,answer_seconds=round(time.monotonic()-started,3),
                          completed_answers=len(answers),persisted_pairs=len(persisted),
                          selected_memory_used=True,preview='session-memory-choices-preview.png',
                          preview_kind='Rendered actual off-screen widgets with authored content; not a desktop screenshot')
            worker.submit('What button color did we choose in that calculator?')
            wait_for(worker,lambda:len([value for kind,value in events if kind=='answer'])>1,root)
            followup=[value for kind,value in events if kind=='answer'][-1]
            result.update(followup_answer=followup,
                followup_source=result['sent_context']['context_source'],
                persisted_pairs=len(store.turns(worker.session_id)))
            result['passed']=bool('purple' in followup.casefold() and 'blue' not in followup.casefold()
                                  and result['followup_source']=='current_session' and result['persisted_pairs']==2)
            if not result['passed']:
                raise AssertionError('Current-session follow-up did not retain selected context: '+followup)
            print(json.dumps(result,indent=2),flush=True)
        finally:
            worker.close(); app.desk.close(); root.destroy()
            (output/'session-context-live-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': main()
