"""Interactive island cards; UI navigation never owns or cancels a task."""
import base64
import io
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageTk
from .island_games import Game, GAMES, HELP
from .island_media import MediaJobs

BG, CARD, TEXT, MUTED, ACCENT = '#08080a','#141419','#efeff4','#a2a2b0','#b4a1ff'


def text(parent, value='', **kw):
    return tk.Label(parent,text=value,bg=kw.pop('bg',BG),fg=kw.pop('fg',TEXT),
                    font=kw.pop('font',('Segoe UI',9)),**kw)


class Approval:
    """Idempotent explicit decision, with cancellation and a bounded lifetime."""
    def __init__(self, payload, now=None):
        self.kind,self.detail,self.answer,self.ready,self.cancelled = payload
        self.created = time.monotonic() if now is None else now
        self.done = False

    def decide(self, approved, now=None):
        if self.done:
            return False
        now = time.monotonic() if now is None else now
        self.done = True
        self.answer['approved'] = bool(approved and not self.cancelled() and now-self.created < 180)
        self.ready.set()
        return self.answer['approved']

    def expired(self, now):
        return self.cancelled() or now-self.created >= 180


class IslandDesk:
    def __init__(self, app, parent):
        self.app = app
        self.frame = tk.Frame(parent,bg=BG)
        self.frame.pack(fill='both',expand=True)
        self.view = 'Overview'
        self.work = {'phase':'Ready','active':False,'target':'','file':'','preview':'','outcome':''}
        self.reply = 'Task results and answers appear here. Games run locally while Jarvis works.'
        self.pending = None
        self.approvals = []
        self.last_poll = self.last_media = self.last_tick = 0.
        self.music = {'error':'Open Spotify and play or request a song to see its verified media session.'}
        self.requested_song = ''
        self.games = {name:Game(name) for name in GAMES}
        self.game = self.games['Flappy']
        self.focus_until = 0.
        self.media = MediaJobs(app.report,Path(__file__).resolve().parent.parent)
        self.now = tk.StringVar(value='Now working · Ready')
        text(self.frame,textvariable=self.now,anchor='w',justify='left',font=('Segoe UI',9,'bold'),
             fg=ACCENT,height=2).pack(fill='x')
        nav = tk.Frame(self.frame,bg=BG)
        nav.pack(fill='x',pady=(2,4))
        self.nav = {}
        for name in ('Overview','Choices','Music','Games','History'):
            button = ttk.Button(nav,text=name,command=lambda n=name:self.show(n),width=8)
            button.pack(side='left',padx=(0,3))
            self.nav[name] = button
        self.content = tk.Frame(self.frame,bg=BG)
        self.content.pack(fill='both',expand=True)
        self.views = {n:tk.Frame(self.content,bg=BG) for n in ('Overview','Choices','Music','Games','History','Settings','Approval')}
        self.history, self.settings = self.views['History'],self.views['Settings']
        overview = self.views['Overview']
        shortcuts = tk.Frame(overview,bg=BG)
        shortcuts.pack(fill='x')
        for caption,question in (("Today's goal","what's my goal today"),('Last task','what was I working on')):
            ttk.Button(shortcuts,text=caption,command=lambda q=question:self.ask(q)).pack(side='left',padx=(0,4))
        self.focus_button = ttk.Button(shortcuts,text='25m focus',command=self.focus)
        self.focus_button.pack(side='right')
        self.overview = ScrolledText(overview,bg=CARD,fg=TEXT,relief='flat',wrap='word',font=('Segoe UI',10),
                                     height=3,padx=10,pady=8,state='disabled')
        self.overview.pack(fill='both',expand=True,pady=(5,0))
        self._write(self.overview,self.reply)
        choices = self.views['Choices']
        self.choice_hint = text(choices,'No pending choices.',anchor='w',fg=MUTED)
        self.choice_hint.pack(fill='x')
        self.choice_canvas = tk.Canvas(choices,bg=BG,highlightthickness=0,height=80)
        scrollbar = ttk.Scrollbar(choices,orient='vertical',command=self.choice_canvas.yview)
        scrollbar.pack(side='right',fill='y')
        self.choice_canvas.pack(side='left',fill='both',expand=True)
        self.choice_canvas.configure(yscrollcommand=scrollbar.set)
        self.choice_rows = tk.Frame(self.choice_canvas,bg=BG)
        self.choice_item = self.choice_canvas.create_window((0,0),window=self.choice_rows,anchor='nw')
        self.choice_rows.bind('<Configure>',lambda _e:self.choice_canvas.configure(scrollregion=self.choice_canvas.bbox('all')))
        self.choice_canvas.bind('<Configure>',lambda e:self.choice_canvas.itemconfigure(self.choice_item,width=e.width))
        self.choice_canvas.bind('<MouseWheel>',lambda e:self.choice_canvas.yview_scroll(-int(e.delta/120),'units'))
        music = self.views['Music']
        self.music_text = text(music,'Spotify',anchor='w',justify='left',wraplength=450)
        self.music_text.pack(fill='x')
        self.cover = text(music,'Artwork unavailable',bg=CARD,fg=MUTED)
        self.cover.pack(fill='both',expand=True,pady=5)
        self.timeline = ttk.Progressbar(music,maximum=100)
        self.timeline.pack(fill='x')
        bar = tk.Frame(music,bg=BG)
        bar.pack(fill='x',pady=(4,0))
        for caption,action in (('Previous','previous'),('Play','play'),('Pause','pause'),('Next','next')):
            ttk.Button(bar,text=caption,command=lambda a=action:self.transport(a),width=8).pack(side='left',padx=(0,3))
        ttk.Button(bar,text='Refresh',command=lambda:self.media.start()).pack(side='right')
        games = self.views['Games']
        bar = tk.Frame(games,bg=BG)
        bar.pack(fill='x')
        self.game_choice = ttk.Combobox(bar,values=GAMES,state='readonly',width=13)
        self.game_choice.set('Flappy')
        self.game_choice.pack(side='left')
        self.game_choice.bind('<<ComboboxSelected>>',lambda _e:self.select_game(self.game_choice.get()))
        ttk.Button(bar,text='Restart',command=self.restart_game,width=7).pack(side='right')
        self.pause_button = ttk.Button(bar,text='Pause',command=self.pause_game,width=7)
        self.pause_button.pack(side='right',padx=3)
        self.game_help = text(games,HELP[self.game.name],fg=MUTED,anchor='w',font=('Segoe UI',8))
        self.game_help.pack(fill='x')
        self.game_canvas = tk.Canvas(games,bg=CARD,highlightthickness=0,takefocus=True,height=280)
        self.game_canvas.pack(fill='both',expand=True)
        self.game_item = self.game_canvas.create_image(0,0,anchor='nw')
        self.game_canvas.bind('<Button-1>',self.game_click)
        self.game_canvas.bind('<KeyPress>',self.game_key)
        self.game_canvas.bind('<FocusOut>',lambda _e:self.app.root.after_idle(self.pause_if_unfocused))
        approval = self.views['Approval']
        self.approval_title = text(approval,'Review this exact action',fg='#f1c580',anchor='w')
        self.approval_title.pack(fill='x')
        self.approval_text = ScrolledText(approval,bg=CARD,fg=TEXT,wrap='word',height=3,state='disabled',font=('Segoe UI',10))
        self.approval_text.pack(fill='both',expand=True)
        bar = tk.Frame(approval,bg=BG)
        bar.pack(fill='x',pady=5)
        self.approve_button = ttk.Button(bar,text='Approve exact action',command=lambda:self.decide(True))
        self.approve_button.pack(side='left')
        ttk.Button(bar,text='Deny',command=lambda:self.decide(False)).pack(side='left',padx=5)
        self.show('Overview')

    @staticmethod
    def _write(widget,value):
        widget.configure(state='normal')
        widget.delete('1.0','end')
        widget.insert('end',value)
        widget.configure(state='disabled')

    def ask(self, question):
        from .commands import Command
        self.app.actions.submit(Command('ask',question))

    def focus(self):
        self.focus_until = 0. if self.focus_until else time.monotonic()+25*60
        self.focus_button.configure(text='Stop focus' if self.focus_until else '25m focus')

    def show(self,name):
        if name not in self.views:
            return
        if self.approvals:
            name = 'Approval'
        if self.view=='Games' and name!='Games':
            self.suspend_game()
        for frame in self.views.values():
            frame.pack_forget()
        self.view = name
        self.views[name].pack(fill='both',expand=True)
        for key,button in self.nav.items():
            button.configure(style='Accent.TButton' if key==name else 'TButton')
        if name=='Music' and not self.app.config.get('_ui_verification',False):
            self.media.start()
        if name=='Games':
            self.game_canvas.focus_set()
        self.refresh_overview()

    def select_game(self,name):
        self.game = self.games[name]
        self.game_choice.set(name)
        self.game_help.configure(text=HELP[name])
        self.pause_button.configure(text='Resume' if self.game.paused else 'Pause')
        self.game_canvas.focus_set()
        self.draw_game()

    def restart_game(self):
        self.game.reset()
        self.pause_button.configure(text='Pause')
        self.game_canvas.focus_set()
        self.draw_game()

    def suspend_game(self):
        self.game.paused = True
        self.pause_button.configure(text='Resume')

    def pause_if_unfocused(self):
        if self.view=='Games' and self.app.root.focus_get()!=self.game_canvas:
            self.suspend_game()

    def pause_game(self):
        self.game.paused = not self.game.paused
        self.pause_button.configure(text='Resume' if self.game.paused else 'Pause')
        self.game_canvas.focus_set()
        self.draw_game()

    def game_click(self,event):
        self.game_canvas.focus_set()
        width,height = max(1,self.game_canvas.winfo_width()),max(1,self.game_canvas.winfo_height())
        self.game.click(event.x*480/width,event.y*280/height)
        self.draw_game()

    def game_key(self,event):
        self.game.key(event.keysym)
        self.draw_game()
        return 'break'  # Space/arrow keys never reach the island toggle or command input.

    def draw_game(self):
        width,height = max(1,self.game_canvas.winfo_width()),max(1,self.game_canvas.winfo_height())
        self.game_canvas.preview_image = self.game.render().resize((width,height),Image.Resampling.LANCZOS)
        self.game_photo = ImageTk.PhotoImage(self.game_canvas.preview_image,master=self.app.root)
        self.game_canvas.itemconfigure(self.game_item,image=self.game_photo)

    def notify(self,kind,value):
        if kind=='task_status' and isinstance(value,dict):
            if value.get('active') and not self.work['active']:
                self.work = {'file':'','preview':'','outcome':'','target':'','phase':'','active':True}
            if value.get('target'):
                self.work['target'] = value['target']
            for key in ('phase','active','file','preview','characters','outcome'):
                if key in value:
                    self.work[key] = value[key]
            self.refresh_overview()
        elif kind in {'answer','spoken_reply','action','warning','command_output'} and isinstance(value,str):
            self.reply = value[-4000:]
            self.refresh_overview()
            if self.view not in {'Games','Approval','Choices','Music'}:
                self.show('Overview')
        elif kind in {'brain','tool','plan'} and isinstance(value,str):
            self.work['activity'] = value[:300]
            self.refresh_overview()
        elif kind=='island_navigation':
            view,game = value
            if game.startswith('@'):
                if game=='@restart':
                    self.restart_game()
                else:
                    self.game.paused = game!='@resume'
                    self.pause_button.configure(text='Resume' if self.game.paused else 'Pause')
                if game=='@stop':
                    view='Overview'
            elif game:
                self.select_game(game)
            self.show(view)
            self.app.show_panel()
        elif kind=='island_music_request':
            self.requested_song = str(value)[:300]
            self.show('Music')
            self.app.show_panel()
        elif kind=='island_media' and isinstance(value,dict):
            if 'transport_message' in value:
                self.music_text.configure(text=value['transport_message'])
                self.last_media = 0.
            else:
                self.music = value
                self.update_music()
        elif kind=='island_transport':
            self.send_transport(value)
        elif kind=='approval':
            self.add_approval(value)

    def refresh_overview(self):
        file = self.work.get('file') or self.work.get('target') or 'No file selected'
        result = self.work.get('outcome','')
        self._write(self.overview,self.reply + '\n\nCURRENT WORK\n' + self.work.get('phase','Ready') +
                    '\n' + file + ('\n'+self.work['activity'] if self.work.get('activity') else '') +
                    ('\n'+result if result else '') + ('\n\nOUTPUT PREVIEW\n'+self.work['preview'] if self.work.get('preview') else ''))

    def update_choices(self,pending):
        if (pending or {}).get('token') == (self.pending or {}).get('token'):
            return
        self.pending = pending
        for child in self.choice_rows.winfo_children():
            child.destroy()
        self.choice_images = []
        self.choice_buttons = []
        self.choice_hint.configure(text='Click or say the option name / number. Choices expire.' if pending else 'No pending choices. Ask for a fresh list.')
        if not pending:
            return
        for index,option in enumerate(pending['options']):
            row = tk.Frame(self.choice_rows,bg=CARD)
            row.pack(fill='x',pady=3)
            photo = self.decode_image(option.get('image',''),(48,48))
            if photo:
                self.choice_images.append(photo)
                artwork = text(row,image=photo,bg=CARD)
                artwork.preview_image = photo.preview_image
                artwork.pack(side='left',padx=5)
            else:
                text(row,str(index+1),bg=CARD,fg=ACCENT,width=3).pack(side='left')
            button = tk.Button(row,text=option['label'],bg=CARD,fg=TEXT,relief='flat',anchor='w',
                activebackground='#302c49',activeforeground=TEXT,wraplength=380,justify='left',
                command=lambda i=index,t=pending['token']:self.choose(t,i),font=('Segoe UI',10),padx=7,pady=7)
            button.pack(side='left',fill='x',expand=True)
            self.choice_buttons.append(button)
        self.show('Choices')
        self.app.show_panel()

    def choose(self,token,index):
        from .commands import Command
        self.app.actions.submit(Command('island_choice',str(index),token))

    def decode_image(self,encoded,size):
        if not encoded or len(encoded)>400_000:
            return None
        try:
            raw = base64.b64decode(encoded,validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.width*image.height>4_000_000:
                    return None
                image.thumbnail(size)
                source = image.convert('RGB')
                photo = ImageTk.PhotoImage(source,master=self.app.root)
                photo.preview_image = source
                return photo
        except (ValueError,OSError,Image.DecompressionBombError):
            return None

    def update_music(self):
        requested = ('Requested: '+self.requested_song+'\n') if self.requested_song else ''
        if self.music.get('error'):
            self.music_text.configure(text=requested + self.music['error'])
            self.cover.configure(image='',text='Artwork unavailable')
            self.cover.preview_image = None
            self.timeline['value'] = 0
            return
        position,duration = self.music.get('position',0),self.music.get('duration',0)
        clock = lambda seconds:f'{int(seconds)//60}:{int(seconds)%60:02d}'
        self.music_text.configure(text=requested + 'Windows reports: ' + self.music.get('title','Unknown track') + ' · '+
            self.music.get('artist','Unknown artist')+'\n'+self.music.get('status','')+' · '+clock(position)+' / '+clock(duration))
        self.timeline['value'] = 100*min(1,position/duration) if duration else 0
        self.cover_photo = self.decode_image(self.music.get('image',''),(164,164))
        self.cover.configure(image=self.cover_photo or '',text='' if self.cover_photo else 'Artwork unavailable')
        self.cover.preview_image = self.cover_photo.preview_image if self.cover_photo else None

    def transport(self,action):
        from .commands import Command
        self.app.actions.submit(Command('spotify_control',action,'island'))

    def send_transport(self,action):
        if self.media.start(action):
            self.music_text.configure(text='Sending Spotify '+action+' once…')
        else:
            self.music_text.configure(text='A Spotify request is in progress. Wait for its result.')

    def add_approval(self,payload):
        approval = Approval(payload)
        if approval.expired(time.monotonic()):
            approval.decide(False)
            return
        self.approvals.append(approval)
        self.render_approval()
        self.app.show_panel()

    def render_approval(self):
        if not self.approvals:
            self.show('Overview')
            return
        approval = self.approvals[0]
        prompt = ('Move this exact file to the Recycle Bin?' if approval.kind=='delete' else
                  'Run this exact command? It can change or delete files.\nWorking folder: '+str(self.app.actions.root)
                  if approval.kind=='command' else 'Approve this exact external action? Review its destination and content.')
        self.approval_title.configure(text='Approval required · '+approval.kind.replace('_',' '))
        self._write(self.approval_text,prompt+'\n\n'+approval.detail)
        self.show('Approval')

    def decide(self,approved):
        if self.approvals:
            self.approvals.pop(0).decide(approved)
            self.render_approval()

    def tick(self, visible):
        now = time.monotonic()
        dt = now-self.last_tick if self.last_tick else 0.
        self.last_tick = now
        for approval in self.approvals[:]:
            if approval.expired(now):
                approval.decide(False)
                self.approvals.remove(approval)
                self.render_approval()
        if now-self.last_poll >= .3:
            self.last_poll = now
            from .island_choices import snapshot
            self.update_choices(snapshot(self.app.actions))
            target = self.work.get('file') or self.work.get('target','')
            caption = ('Now working' if self.work.get('active') else 'Last work')+' · '+self.work.get('phase','Ready')
            caption += '\n'+(Path(target).name if target else 'No file selected')[:90]
            if self.work.get('characters'):
                caption += ' · '+str(self.work['characters'])+' chars'
            if self.focus_until:
                remaining = max(0,int(self.focus_until-now))
                caption += f' · Focus {remaining//60}:{remaining%60:02d}'
                if not remaining:
                    self.focus_until = 0.
                    self.focus_button.configure(text='25m focus')
                    self.app.report('answer','Your 25-minute focus timer is complete.')
            self.now.set(caption)
            if 'expires' in (self.pending or {}):
                self.choice_hint.configure(text=f'Click or say the name / number · {max(0,int(self.pending["expires"]-now))}s remaining')
        if visible and self.view=='Games':
            self.game.tick(dt)
            self.draw_game()
        if visible and self.view=='Music' and now-self.last_media>=5 and not self.app.config.get('_ui_verification',False):
            if self.media.start():
                self.last_media = now

    def cancel_approvals(self):
        for approval in self.approvals:
            approval.decide(False)
        self.approvals.clear()
        if self.view=='Approval':
            self.show('Overview')

    def close(self):
        self.cancel_approvals()
        self.media.close()
