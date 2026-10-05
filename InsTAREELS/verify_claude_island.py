"""Authored Claude stream replay in actual off-screen Tk island widgets."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tkinter as tk
from unittest.mock import patch

BASE=Path(__file__).resolve().parent

if __name__=='__main__':
    previous=os.environ.get('JARVIS_UI_VERIFY');os.environ['JARVIS_UI_VERIFY']='1'
    from main import App
    from jarvis.claude_code import event_progress
    from jarvis.ui_preview import export_preview
    from verify_notch import keyed
    root=tk.Tk();root.withdraw();app=None
    try:
        app=App(root)
        for callback in root.tk.call('after','info'):root.after_cancel(callback)
        root.geometry('402x40+20000+20000');root.deiconify()
        app.question.set('Edit main.cpp in the selected project to add keyboard controls')
        clock=[100.];heights=[]
        def tick():
            clock[0]+=1/30
            with patch('jarvis.island.time.monotonic',return_value=clock[0]):app.island.tick('THINKING')
            root.update()
            heights.append(root.winfo_height())
        def report(kind,value):app.island.notify(kind,value);app.desk.notify(kind,value)
        project=Path('D:/Projects/Authored Example');pending={}
        report('task_status',{'phase':'Opening Claude Code project','target':str(project),'active':True,'reveal':True})
        for _ in range(20):tick()
        view=app.desk.views['Overview'];assert view.winfo_ismapped(),'Live preview was not revealed'
        children=tuple(view.winfo_children());unmaps=[]
        view.bind('<Unmap>',lambda e:unmaps.append(e.widget),add='+')
        with patch.object(app,'layout_notch',wraps=app.layout_notch) as layout:
            for n in range(90):
                event_progress({'type':'stream_event','event':{'delta':{'type':'text_delta','text':f'Observed file update {n}: preparing keyboard controls.\n'}}},report,project,pending)
                tick()
            assert layout.call_count==0
        assert not unmaps and tuple(view.winfo_children())==children
        event_progress({'type':'assistant','message':{'content':[{'type':'tool_use','id':'edit1','name':'Edit','input':{'file_path':str(project/'main.cpp'),'new_string':'// Authored source preview, not executed\nvoid onKey(int key) { /* requested controls */ }'}}]}},report,project,pending)
        for _ in range(15):tick()
        assert all(b>=a for a,b in zip(heights,heights[1:])),'Coding phase change collapsed the island'
        target=BASE/'artifacts/claude-code-island-preview.png';export_preview(app,target)
        from PIL import Image
        keyed(Image.open(target)).save(target)
        report('task_status',{'phase':'Claude Code session ended','target':str(project),'active':False})
        for _ in range(15):tick()
        report('answer','main.cpp updated; disk readback passed, runtime checks pending.')
        for _ in range(20):tick()
        assert all(b>=a for a,b in zip(heights,heights[1:])),'Completion handoff collapsed the island'
        assert not unmaps and tuple(view.winfo_children())==children
        record={'date':datetime.now(timezone.utc).isoformat(),'passed':True,
            'scope':'Authored CLI event replay in real off-screen Tk widgets; rendered preview, not desktop screenshot or live inference.',
            'stream_updates':90,'view_unmaps':len(unmaps),'layout_rebuilds':layout.call_count,'widgets_preserved':True,
            'monotonic_growth':True,
            'completion_handoff_preserved':True,
            'preview':'artifacts/claude-code-island-preview.png'}
        (BASE/'artifacts/claude-code-island-check.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record,indent=2))
    finally:
        if app:app.close()
        else:root.destroy()
        if previous is None:os.environ.pop('JARVIS_UI_VERIFY',None)
        else:os.environ['JARVIS_UI_VERIFY']=previous
