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

BG, CARD, TEXT, MUTED, ACCENT = '#000000','#151515','#eeeeee','#909090','#b4caff'


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
        self.has_reply = False
        self.answer_phase = ''
        self.work = {'phase':'Ready','active':False,'target':'','file':'','preview':'','outcome':''}
        self.reply = 'Task results and answers appear here. Games run locally while Jarvis works.'
        self.full_reply = self.reply
        self.pending = None
        self.prepared = []
        self.prepared_token = ''
        self.approvals = []
        self.last_poll = self.last_media = self.last_tick = 0.
        self.music = {'error':'Open Spotify and play or request a song to see its verified media session.'}
        self.requested_song = ''
        self.games = {name:Game(name) for name in GAMES}
        self.game = self.games['Flappy']
        self.focus_until = 0.
        self.media = MediaJobs(app.report,Path(__file__).resolve().parent.parent)
        self.now = tk.StringVar(value='Now working · Ready')
        self.status_label = text(self.frame,textvariable=self.now,anchor='w',justify='left',font=('Segoe UI',9,'bold'),
             fg=ACCENT,height=2)
        self.status_label.pack(fill='x')
        nav = self.nav_frame = tk.Frame(self.frame,bg=BG)
        nav.pack(fill='x',pady=(2,4))
        self.nav = {}
        for name in ('Overview','Prepared','Choices','Music','Games','History'):
            button = ttk.Button(nav,text=name,command=lambda n=name:self.show(n,reveal=True),width=7)
            button.pack(side='left',padx=(0,3))
            self.nav[name] = button
        self.content = tk.Frame(self.frame,bg=BG)
        self.content.pack(fill='both',expand=True)
        self.views = {n:tk.Frame(self.content,bg=BG) for n in ('Overview','Prepared','Choices','Music','Games','History','Settings','Approval','Console')}
        self.history, self.settings = self.views['History'],self.views['Settings']
        overview = self.views['Overview']
        shortcuts = self.shortcuts = tk.Frame(overview,bg=BG)
        shortcuts.pack(fill='x')
        for caption,question in (("Today's goal","what's my goal today"),('Last task','what was I working on')):
            ttk.Button(shortcuts,text=caption,command=lambda q=question:self.ask(q)).pack(side='left',padx=(0,4))
        self.focus_button = ttk.Button(shortcuts,text='25m focus',command=self.focus)
        self.focus_button.pack(side='right')
        from .notch_widgets import RoundedCard
        self.answer_card = RoundedCard(overview, radius=24)
        self.answer_card.pack(fill='both',expand=True,pady=(8,0))
        answer_header = tk.Frame(self.answer_card.content,bg=CARD)
        answer_header.pack(fill='x',pady=(0,8))
        self.answer_title = text(answer_header,'Jarvis · Answer',bg=CARD,fg=MUTED,anchor='w')
        self.answer_title.pack(side='left')
        ttk.Button(answer_header,text='Copy',width=6,command=self.copy_answer,style='Card.TButton').pack(side='right')
        self.overview = ScrolledText(self.answer_card.content,bg=CARD,fg=TEXT,relief='flat',wrap='word',font=('Segoe UI',11),
                                     height=3,padx=6,pady=4,state='disabled',borderwidth=0)
        self.overview.pack(fill='both',expand=True)
        self.overview.tag_configure('code',font=('Consolas',10),foreground='#c6d7ed')
        self._write(self.overview,self.reply)
        prepared = self.views['Prepared']
        self.prepared_hint = text(prepared,'Useful work prepared during idle time. Predictions need review.',
                                  anchor='w',justify='left',wraplength=450,fg=MUTED)
        self.prepared_hint.pack(fill='x')
        self.prepared_choice = ttk.Combobox(prepared,state='readonly')
        self.prepared_choice.pack(fill='x',pady=4)
        self.prepared_choice.bind('<<ComboboxSelected>>',lambda _e:self.select_preparation())
        self.prepared_text = ScrolledText(prepared,bg=CARD,fg=TEXT,relief='flat',wrap='word',
            font=('Segoe UI',10),height=5,padx=10,pady=8,state='disabled')
        self.prepared_text.pack(fill='both',expand=True)
        controls = tk.Frame(prepared,bg=BG)
        controls.pack(fill='x',pady=4)
        self.prepared_accept = ttk.Button(controls,text='Accept',command=lambda:self.preparation_action('accept'))
        self.prepared_accept.pack(side='left',padx=(0,4))
        self.prepared_dismiss = ttk.Button(controls,text='Dismiss',command=lambda:self.preparation_action('dismiss'))
        self.prepared_dismiss.pack(side='left',padx=(0,4))
        ttk.Button(controls,text='Pause anticipation',command=lambda:self.preparation_action('pause')).pack(side='right')
        self.update_preparations({'preparations':[]})
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
        previous = widget.get('1.0','end-1c')
        if previous == value:
            return  # Preserve selection and scrolling when only navigation changes.
        view = widget.yview()
        follow = view[1] >= .98
        anchor = widget.index('@0,0')
        appended = bool(previous and value.startswith(previous))
        widget.configure(state='normal')
        if appended:
            widget.insert('end', value[len(previous):])
        else:
            widget.delete('1.0','end')
            widget.insert('end',value)
        widget.configure(state='disabled')
        if follow:
            widget.see('end')
        elif not appended:
            widget.yview(anchor)

    def ask(self, question):
        from .commands import Command
        self.app.actions.submit(Command('ask',question))

    def update_preparations(self, value):
        selected = self.prepared_token
        self.prepared = value.get('preparations', [])
        self.prepared_choice.configure(values=[row['topic']+' · '+row['status'] for row in self.prepared])
        index = next((i for i,row in enumerate(self.prepared) if row['id']==selected),
                     len(self.prepared)-1)
        if index >= 0:
            self.prepared_choice.current(index)
        else:
            self.prepared_choice.set('No current preparations')
        self.prepared_hint.configure(text='Anticipation paused.' if value.get('paused') else
            'Storage needs review.' if value.get('storage_failed') else
            'Idle preparations · review the evidence and unanswered questions.')
        self.select_preparation()

    def select_preparation(self):
        index = self.prepared_choice.current()
        row = self.prepared[index] if 0 <= index < len(self.prepared) else None
        self.prepared_token = row['id'] if row else ''
        for button in (self.prepared_accept,self.prepared_dismiss):
            button.configure(state='normal' if row and row['status'] in {'suggested','prepared'} else 'disabled')
        if row:
            remaining = max(0,int(row['expires']-time.time()))
            detail = (row['topic']+'\n\nEvidence: '+row['evidence']+'\nMode: '+row['mode']+
                ' · '+row['status']+f'\nExpires in {remaining//60}m {remaining%60}s\n\n'+
                (row.get('content') or 'Likely useful next step: prepare a source comparison and research questions.'
                 if row['kind']=='research' else row.get('content') or
                 'Likely useful next step: prepare a review checklist. No source will be edited.'))
        else:
            detail = ('No current prepared work. Research/search requests can prepare evidence after Jarvis is idle. '
                      'Inferred browser/editor needs appear here for acceptance. Say "resume anticipation" if paused.')
        self._write(self.prepared_text,detail)

    def preparation_action(self, action):
        from .commands import Command
        if action in {'accept','dismiss'} and not self.prepared_token:
            return
        self.app.actions.submit(Command('anticipation',action,self.prepared_token))

    def focus(self):
        self.focus_until = 0. if self.focus_until else time.monotonic()+25*60
        self.focus_button.configure(text='Stop focus' if self.focus_until else '25m focus')

    def show(self,name,reveal=False):
        if name not in self.views:
            return
        if self.approvals:
            name = 'Approval'
        if reveal or name != 'Overview':
            self.app.island.features_open = True
        if name == self.view and self.views[name].winfo_manager() == 'pack':
            return  # Stream updates change text, never unmount the current view.
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

    def copy_answer(self):
        # Copy the full result, including code whitespace, without opening a reader.
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(self.full_reply)

    def chrome(self, visible):
        if getattr(self, '_chrome_visible', None) == visible:
            return
        self._chrome_visible = visible
        self.status_label.pack_forget()
        self.nav_frame.pack_forget()
        self.shortcuts.pack_forget()
        if visible:
            self.status_label.pack(fill='x',before=self.content)
            self.nav_frame.pack(fill='x',pady=(2,4),before=self.content)
            self.shortcuts.pack(fill='x',before=self.answer_card)

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
        # A mouse press focuses Pause before its release invokes pause_game.
        # Auto-pausing there would make that one click toggle straight back to
        # running. Keep the explicit transport button in the game focus group.
        if self.view=='Games' and self.app.root.focus_get() not in (self.game_canvas, self.pause_button):
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
        if kind=='anticipation' and isinstance(value,dict):
            self.update_preparations(value)
        elif kind=='anticipation_reply' and isinstance(value,str):
            self._write(self.prepared_text,value)
        elif kind=='task_status' and isinstance(value,dict):
            if value.get('active') and not self.work['active']:
                self.work = {'file':'','preview':'','outcome':'','target':'','phase':'','active':True}
                self.reply = self.full_reply = ''
                self.has_reply = False
            if value.get('target'):
                self.work['target'] = value['target']
            for key in ('phase','active','file','preview','characters','outcome'):
                if key in value:
                    self.work[key] = value[key]
            self.refresh_overview()
        elif kind == 'answer_stream' and isinstance(value, dict):
            self.answer_phase = value.get('phase', 'Generating answer') + (' · incomplete' if value.get('active', True) else '')
            if 'text' in value:
                self.reply = value['text'][:64000]
                self.full_reply = value['text']
            self.has_reply = True
            self.refresh_overview()
            if self.view not in {'Games','Approval','Choices','Music','Console','Settings','History','Prepared'}:
                self.show('Overview')
        elif kind == 'answer_error' and isinstance(value, str):
            self.answer_phase = 'Interrupted · incomplete'
            self.reply = (self.reply + '\n\n' + value).strip()[:64000]
            self.has_reply = True
            self.refresh_overview()
        elif kind in {'answer','spoken_reply','action','warning','command_output'} and isinstance(value,str):
            self.answer_phase = ''
            self.reply = value[:64000]
            self.full_reply = value
            self.has_reply = True
            self.refresh_overview()
            if self.view not in {'Games','Approval','Choices','Music','Console','Settings','History','Prepared'}:
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
        work = ('CURRENT WORK\n' + self.work.get('phase','Ready') + '\n' + file +
                ('\n'+self.work['activity'] if self.work.get('activity') else '') +
                ('\n'+result if result else '') + ('\n\nOUTPUT PREVIEW\n'+self.work['preview'] if self.work.get('preview') else ''))
        self._write(self.overview,(work+'\n\n'+self.reply).strip() if self.work.get('active') else
                    self.reply+('\n\n'+work if self.work.get('target') else ''))
        active = self.work.get('active')
        title = 'Jarvis · '+(self.answer_phase or ('Working' if active else 'Answer'))
        if self.answer_title.cget('text') != title:
            self.answer_title.configure(text=title)
        content = self.overview.get('1.0','end-1c')
        # Fenced code keeps its indentation and gets a readable mono face.
        start, inside = None, False
        for index, line in enumerate(content.splitlines(), 1):
            if line.lstrip().startswith('```'):
                if inside:
                    self.overview.tag_add('code',start,f'{index}.end')
                else:
                    start = f'{index}.0'
                inside = not inside
        if inside:
            self.overview.tag_add('code',start,'end')

    def update_choices(self,pending):
        if (pending or {}).get('token') == (self.pending or {}).get('token'):
            return
        self.pending = pending
        for child in self.choice_rows.winfo_children():
            child.destroy()
        self.choice_images = []
        self.choice_buttons = []
        self.choice_hint.configure(text=((pending.get('question','')+'\n') if pending and pending.get('kind')=='whatsapp' else '')+
                                   ('Click or say the option name / number. Choices expire.' if pending else 'No pending choices. Ask for a fresh list.'),
                                   wraplength=420,justify='left')
        if not pending:
            return
        for index,option in enumerate(pending['options']):
            row = tk.Frame(self.choice_rows,bg=CARD)
            row.pack(fill='x',pady=3)
            header = tk.Frame(row,bg=CARD)
            header.pack(fill='x')
            photo = self.decode_image(option.get('image',''),(48,48))
            if photo:
                self.choice_images.append(photo)
                artwork = text(header,image=photo,bg=CARD)
                artwork.preview_image = photo.preview_image
                artwork.pack(side='left',padx=5)
            else:
                text(header,str(index+1),bg=CARD,fg=ACCENT,width=3).pack(side='left')
            from .glass_ui import GlassButton
            button = GlassButton(header,text=option['label'],bg=CARD,fg=TEXT,anchor='w',
                activebackground='#302c49',activeforeground=TEXT,wraplength=380,justify='left',
                command=lambda i=index,t=pending['token']:self.choose(t,i),font=('Segoe UI',10),padx=7,pady=7)
            button.pack(side='left',fill='x',expand=True)
            self.choice_buttons.append(button)
            if option.get('context'):
                text(row,option['context'],bg=CARD,fg=MUTED,anchor='w',justify='left',wraplength=390).pack(
                    side='bottom',fill='x',padx=10,pady=(0,8))
        self.show('Choices')
        self.app.show_panel()

    def choose(self,token,index):
        from .commands import Command
        kind = 'memory_choice' if self.pending and self.pending.get('kind') == 'memory' else 'island_choice'
        self.app.actions.submit(Command(kind,str(index),token))

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
                question = (self.pending.get('question','')+'\n') if self.pending.get('kind')=='whatsapp' else ''
                self.choice_hint.configure(text=question+f'Click or say the name / number · {max(0,int(self.pending["expires"]-now))}s remaining')
        if visible and self.view=='Games':
            if self.game.started and not self.game.paused and not self.game.over:
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
