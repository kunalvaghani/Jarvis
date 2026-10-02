"""Exercise actual island cards with a temporary background coding fixture.

Exports only rendered Jarvis widgets. Never captures the desktop, starts a mic,
queries Spotify, plays music, calls inference or writes the real memory vault.
"""
import argparse
import base64
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import tkinter as tk
import time

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('artifacts/island-desk-check.json'))
    args = parser.parse_args()
    previous = os.environ.get('JARVIS_UI_VERIFY')
    os.environ['JARVIS_UI_VERIFY']='1'
    from main import App
    from jarvis.code_stream import CodeDraft
    from jarvis.commands import parse
    from jarvis.island import font
    from jarvis.island_games import GAMES
    from jarvis.ui_preview import export_preview
    root = tk.Tk(); root.withdraw()
    app = None
    checks = {}
    finished = threading.Event()
    output = args.output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    try:
        app = App(root)
        app.panel.geometry('720x820+20000+20000')
        app.panel.deiconify()
        app.live.set('Sample cards · background coding fixture')
        app.speech.options['enabled']=False
        app.actions.task_active=True
        generation=app.actions.generation
        with tempfile.TemporaryDirectory(prefix='jarvis-island-fixture-') as directory:
            target=Path(directory)/'preview_demo.py'
            errors=[]
            def coding():
                try:
                    draft=CodeDraft(directory,target,None,True,'# Temporary UI verification fixture\n',lambda:False,app.report)
                    for content in ('def greeting():\n','def greeting():\n    return ', 'def greeting():\n    return "Hello from the island"\n'):
                        draft.write(content)
                        finished.wait(.1)
                    observed=target.read_text(encoding='utf-8')
                    compile(observed,str(target),'exec')
                    checks['background_file_readback_and_syntax']=True
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    finished.set()
            worker=threading.Thread(target=coding,name='island-coding-fixture')
            worker.start()
            app.actions.submit(parse('play 2048 game'))
            deadline=time.monotonic()+5
            while not finished.is_set() and time.monotonic()<deadline:
                root.update()
                time.sleep(.015)
            worker.join(timeout=1)
            if errors or worker.is_alive():
                raise ValueError('Background fixture failed: '+str(errors))
            app.drain()
            checks['game_navigation_preserved_generation']=app.actions.generation==generation
            checks['game_opened_during_background_work']=app.desk.view=='Games'
            checks['current_file_received']=app.desk.work.get('file')==str(target)
            checks['draft_not_claimed_saved']=app.desk.work.get('outcome')=='Incomplete draft'
            # Scrub the temporary host path in the documented sample.
            app.desk.reply='The temporary coding fixture is running. This is sample output, not a completed user task.'
            app.desk.notify('task_status',{'phase':'Writing 47 chars','target':'D:/Demo/preview_demo.py',
                'file':'D:/Demo/preview_demo.py','preview':'def greeting():\n    return "Hello from the island"',
                'characters':47,'outcome':'Incomplete draft','active':True})
            app.actions.task_active=False
            captures=[]
            for view in ('Overview','Games','Music','Choices'):
                if view=='Games':
                    app.desk.select_game('2048')
                    app.desk.game.grid=[[2,4,8,0],[4,8,16,0],[0,32,64,0],[0,0,0,0]]
                    app.desk.game.score=128
                elif view=='Music':
                    art=Image.new('RGB',(164,164),'#403665')
                    ImageDraw.Draw(art).text((82,82),'DEMO',font=font(28,True),fill='#d5c6ff',anchor='mm')
                    buffer=io.BytesIO(); art.save(buffer,format='PNG')
                    encoded=base64.b64encode(buffer.getvalue()).decode('ascii')
                    app.desk.requested_song='Sample song (fixture)'
                    app.desk.notify('island_media',{'title':'Sample song','artist':'Demo artist','status':'paused',
                        'position':42,'duration':180,'image':encoded})
                elif view=='Choices':
                    app.desk.update_choices({'token':'sample-non-executable','kind':'control','expires':time.monotonic()+45,
                        'options':[{'label':'Sample song · Demo artist · Studio version','image':encoded},
                                   {'label':'Sample song · Demo artist · Live version','image':encoded}]})
                app.desk.show(view)
                app.panel.geometry('720x820+20000+20000')
                app.panel.deiconify()
                root.update_idletasks()
                if not app.preview.winfo_ismapped() or not app.desk.views[view].winfo_ismapped():
                    raise ValueError('Preview widgets were not mapped for '+view)
                app.desk.draw_game()
                # Manual card rendering while root remains hidden; no external observation.
                app.desk.now.set('Now working · Writing 47 chars\npreview_demo.py · Incomplete draft')
                path=output.parent/('island-desk-'+view.lower()+'.png')
                export_preview(app,path)
                captures.append((view,path))
            montage=Image.new('RGB',(1500,1800),'#16171c')
            draw=ImageDraw.Draw(montage)
            draw.text((35,18),'JARVIS / INTERACTIVE ISLAND',font=font(28,True),fill='#eeeef4')
            draw.text((35,58),'Rendered runtime widgets with sample data · not desktop screenshots or live Spotify results',font=font(16),fill='#aaaabb')
            for index,(view,path) in enumerate(captures):
                x,y=20+(index%2)*750,110+(index//2)*845
                draw.text((x,y-26),view,font=font(18,True),fill='#b4a1ff')
                with Image.open(path) as image:
                    montage.paste(image,(x,y))
            montage.save(output.parent/'island-desk-preview.png')
            for name in GAMES:
                app.desk.select_game(name)
                checks['renders_'+name]=app.desk.game.render().size==(480,280)
            ready=threading.Event(); answer={}
            app.desk.add_approval(('delete','D:/Demo/exact-fixture.txt',answer,ready,lambda:False))
            checks['approval_nonblocking']=not ready.is_set() and app.desk.view=='Approval'
            app.desk.decide(False)
            checks['approval_denied']=ready.is_set() and answer.get('approved') is False
            checks['microphone_not_started']=app.listener is None
            checks['real_memory_disabled']=app.config['memory']['enabled'] is False
            if not all(checks.values()):
                raise ValueError('Island checks failed: '+str(checks))
    finally:
        if app: app.close()
        else: root.destroy()
        if previous is None: os.environ.pop('JARVIS_UI_VERIFY',None)
        else: os.environ['JARVIS_UI_VERIFY']=previous
    result={'at':datetime.now(timezone.utc).isoformat(),'scope':'Hidden native UI + temporary background file fixture; no model, media playback, desktop capture or real-vault writes',
            'checks':checks,'live_spotify_playback_tested':False,'live_voice_tested':False}
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
