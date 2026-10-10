"""Compact island controls connected to the existing Jarvis lifecycle."""
import os
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from .island import Island, KEY, BLACK
from .display import window_scale
from .notch_widgets import NotchPanel, RoundedCard

BG = BLACK
CARD = '#151515'
LINE = '#2d2d2d'
CYAN = '#b4caff'
TEXT = '#efeff4'
MUTED = '#a2a2b0'


def label(parent, text='', **kwargs):
    return tk.Label(parent, text=text, bg=kwargs.pop('bg', BG), fg=kwargs.pop('fg', TEXT),
                    font=kwargs.pop('font', ('Segoe UI', 10)), **kwargs)


def build_interface(app):
    root = app.root
    scale = window_scale(root)
    root.title('Jarvis Dynamic Island')
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.configure(bg=KEY)
    try:
        root.attributes('-transparentcolor', KEY)
    except tk.TclError:
        root.configure(bg=BG)
    root.geometry(f'{round(402*scale)}x{round(40*scale)}+{(root.winfo_screenwidth()-round(402*scale))//2}+0')
    app.island_canvas = tk.Canvas(root, width=208, height=52, bg=KEY, highlightthickness=0, borderwidth=0,
                                  relief='flat', cursor='hand2', takefocus=True)
    app.island_canvas.pack(fill='both', expand=True)
    app.island = Island(app, app.island_canvas)
    app.island_canvas.bind('<Return>', app.toggle_panel)
    app.island_canvas.bind('<space>', app.toggle_panel)
    app.menu = tk.Menu(root, tearoff=False, bg=CARD, fg=TEXT, activebackground=LINE, activeforeground=CYAN)
    for text, command in (('Open Jarvis', app.show_panel), ('Start / stop listening', app.toggle_listening),
                          ('Command prompt', app.show_command_prompt), ('Stop voice', app.speech.cancel),
                          ('Preview typed command', app.preview_command),
                          ('Files', lambda: os.startfile(app.actions.root))):
        app.menu.add_command(label=text, command=command)
    app.menu.add_separator()
    app.menu.add_command(label='Quit Jarvis', command=app.close)
    root.bind('<Escape>', lambda _event: app.hide_panel())
    def track_pointer(_event):
        widget = root.winfo_containing(root.winfo_pointerx(), root.winfo_pointery())
        app.island.hover = widget is not None and widget.winfo_toplevel() == root
    root.bind('<Enter>',track_pointer,add='+')
    root.bind('<Leave>',track_pointer,add='+')
    def retain_control_focus(event):
        if event.widget != app.island_canvas:
            if app.island.surface_open and not app.island.expanded:
                app.show_panel()
            # Expansion must not move focus away from the clicked dropdown/input.
            app.island.focus_pending = False
    root.bind('<Button-1>',retain_control_focus,add='+')

    app.panel = NotchPanel(app)
    try:
        opacity = min(1.,max(.8,float(app.config.get('ui',{}).get('opacity',1.))))
        root.attributes('-alpha',opacity)
    except (tk.TclError,TypeError,ValueError):
        pass

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TButton', font=('Segoe UI', 9), padding=(7, 4), background=LINE, foreground=TEXT,
                    borderwidth=0, focusthickness=1, focuscolor=CYAN)
    style.map('TButton', background=[('active', '#3a3a44'), ('pressed', '#484852')])
    style.configure('Accent.TButton', background='#343a46', foreground='#d5e2ff', font=('Segoe UI', 9, 'bold'))
    style.map('Accent.TButton', background=[('active', '#465168'), ('pressed', '#596986')])
    style.configure('TCheckbutton', background=BG, foreground=TEXT, font=('Segoe UI', 9))
    style.configure('TEntry', fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT, padding=6)
    style.configure('TCombobox', fieldbackground=CARD, foreground=TEXT, background=LINE, arrowcolor=TEXT, padding=4)
    style.map('TCombobox', fieldbackground=[('readonly', CARD)], foreground=[('readonly', TEXT)])
    style.configure('Horizontal.TProgressbar', background='#8bdda8', troughcolor=LINE, borderwidth=0, thickness=2)
    root.option_add('*TCombobox*Listbox.background', CARD)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    from .glass_ui import install_glass
    install_glass(root, style)

    shell = app.panel
    app.hud_status = tk.StringVar(value='STANDBY')
    app.ui_activity = ''
    app.state = tk.StringVar(value='Microphone off')
    app.live = tk.StringVar(value='Ready when you are.')
    app.question = tk.StringVar()
    app.state_label = label(shell, textvariable=app.state, fg=MUTED)
    app.reply_label = label(shell, textvariable=app.live, anchor='w')
    prompt = RoundedCard(shell, height=round(68*scale), radius=24)
    snippet = tk.StringVar()
    app.question_label = label(prompt.content, textvariable=snippet, bg=CARD, justify='left', anchor='w',
        wraplength=round(464*scale), font=('Segoe UI', 11))
    app.question_label.pack(fill='both', expand=True)
    app.question.trace_add('write', lambda *_: snippet.set(app.question.get()[:220]))
    body = tk.Frame(shell, bg=BG)
    from .island_desk import IslandDesk
    app.desk = IslandDesk(app, body)
    app.log = ScrolledText(app.desk.history, height=3, bg=CARD, fg=TEXT, insertbackground=TEXT, relief='flat',
        borderwidth=0, padx=12, pady=10, font=('Segoe UI', 10), state='disabled', wrap='word')
    app.log.pack(fill='both', expand=True)
    app.log.tag_configure('answer', foreground='#d5e2ff')
    app.log.tag_configure('repair', foreground=MUTED)
    utilities = tk.Frame(shell, bg=BG)
    for caption, handler in (('Stop tasks',app.stop),('Stop voice',app.speech.cancel),
                             ('Settings',lambda:app.desk.show('Settings')),('Console',app.show_command_prompt)):
        ttk.Button(utilities,text=caption,command=handler).pack(side='left',padx=(0,4))
    ttk.Button(utilities,text='Quit Jarvis',command=app.close).pack(side='right')
    footer = tk.Frame(shell,bg=BG)
    composer = RoundedCard(footer,height=round(48*scale),radius=24,inset=10)
    composer.pack(fill='x')
    input_text = tk.StringVar()
    app.preview = ttk.Entry(composer.content,font=('Segoe UI',11),textvariable=input_text,style='Card.TEntry')
    app.preview.pack(side='left',fill='both',expand=True)
    app.preview.bind('<Return>',lambda _event:app.send_input())
    placeholder = label(app.preview,'Ask Jarvis anything…',bg='#1b1c21',fg=MUTED,font=('Segoe UI',11),padx=0,pady=0)
    placeholder.bind('<Button-1>',lambda _e:app.preview.focus_set())
    def show_placeholder(*_):
        placeholder.place_forget() if input_text.get() else placeholder.place(x=12,rely=.5,anchor='w')
    input_text.trace_add('write',show_placeholder)
    show_placeholder()
    ttk.Button(composer.content,text='↑',width=3,command=app.send_input,style='Card.TButton').pack(side='right')
    ttk.Button(composer.content,text='•••',width=3,command=lambda:app.desk.show('Overview',reveal=True),style='Card.TButton').pack(side='right',padx=(0,4))
    ttk.Button(composer.content,text='Mic',width=4,command=app.toggle_listening,style='Card.TButton').pack(side='right',padx=(0,4))
    controls = tk.Frame(footer,bg=BG)
    controls.pack(fill='x',pady=(7,0))
    for caption,handler in (('Ask',app.ask_question),('Ask screen',app.ask_screen),('Do task',app.do_task)):
        ttk.Button(controls,text=caption,command=handler).pack(side='left',padx=(0,4))
    ttk.Button(controls,text='Features',command=lambda:app.desk.show('Overview',reveal=True)).pack(side='left')
    app.toggle = ttk.Button(controls,text='Start listening',command=app.toggle_listening)
    app.toggle.pack(side='right')
    app.composer_hint = label(footer,'Type a request  ·  Enter to send  ·  Esc to collapse',fg=MUTED,
                              anchor='w',font=('Segoe UI',9))
    app.composer_hint.pack(fill='x',pady=(6,0))
    def layout(workspace):
        footer.pack(side='bottom',fill='x')
        prompt.pack_forget()
        body.pack_forget()
        utilities.pack_forget()
        controls.pack_forget()
        features = app.island.features_open or app.desk.view != 'Overview'
        app.desk.chrome(features)
        if workspace:
            if features:
                utilities.pack(side='bottom',fill='x',pady=(8,8))
            if app.question.get():
                prompt.pack(side='top',fill='x',pady=(0,8))
            body.pack(fill='both',expand=True)
        if features:
            controls.pack(fill='x',pady=(7,0),before=app.composer_hint)
    app.layout_notch = layout
    settings = app.desk.settings
    app.settings_open = False
    def settings_toggle():
        app.settings_open = not app.settings_open
        app.desk.show('Settings' if app.settings_open else 'Overview')
    label(settings, 'Microphone', fg=MUTED).grid(row=0, column=0, sticky='w', padx=(0, 12))
    app.mic_choice = ttk.Combobox(settings, state='readonly', width=24)
    app.mic_choice.grid(row=0, column=1, sticky='ew')
    app.mic_devices = [None]
    app.mic_choice['values'] = ['System default microphone']
    app.mic_choice.current(0)
    settings.columnconfigure(1, weight=1)
    label(settings, 'Language', fg=MUTED).grid(row=1, column=0, sticky='w', pady=7)
    app.answer_language = ttk.Combobox(settings, state='readonly', width=16, values=['Auto', 'English', 'Hindi'])
    app.answer_language.grid(row=1, column=1, sticky='w')
    app.answer_language.set({'auto':'Auto','en':'English','hi':'Hindi'}.get(app.config.get('knowledge',{}).get('answer_language','auto'),'Auto'))
    app.answer_language.bind('<<ComboboxSelected>>', app.save_speech_settings)
    app.speak_enabled = tk.BooleanVar(value=app.speech.options.get('enabled', True))
    ttk.Checkbutton(settings, text='Speak replies', variable=app.speak_enabled, command=app.save_speech_settings).grid(row=2,column=1,sticky='w')
    app.backend = tk.StringVar(value=f"Whisper {app.config['whisper']['model']}")
    label(settings, textvariable=app.backend, fg=MUTED, wraplength=440, font=('Segoe UI', 8)).grid(row=3,column=0,columnspan=2,sticky='w')
    label(settings,textvariable=app.state,fg=MUTED,anchor='w').grid(row=4,column=0,columnspan=2,sticky='w',pady=10)
    app.level = ttk.Progressbar(settings,maximum=100)
    app.level.grid(row=5,column=0,columnspan=2,sticky='ew')
    console = app.desk.views['Console']
    from .coding_console import CodingConsole
    app.coding_console = CodingConsole(console,code=app.start_native_coding,command=app.run_command,stop=app.actions.cancel)
    coding_row=tk.Frame(console,bg=BG);coding_row.pack(fill='x',pady=4)
    app.coding_goal=ttk.Entry(coding_row);app.coding_goal.pack(side='left',fill='x',expand=True)
    ttk.Button(coding_row,text='Code in folder…',command=app.start_native_coding).pack(side='right')
    label(console,'Command console · '+str(app.actions.root),fg=MUTED,anchor='w',wraplength=440).pack(fill='x',pady=(0,8))
    app.command_output = ScrolledText(console,bg=CARD,fg=TEXT,insertbackground=TEXT,relief='flat',
        font=('Consolas',10),state='disabled',wrap='word',height=3)
    app.command_output.pack(fill='both',expand=True)
    row = tk.Frame(console,bg=BG)
    row.pack(fill='x',pady=(8,0))
    app.command_entry = ttk.Entry(row)
    app.command_entry.pack(side='left',fill='x',expand=True)
    app.command_entry.bind('<Return>',lambda _event:app.run_command())
    ttk.Button(row,text='Run',command=app.run_command).pack(side='right',padx=(8,0))
    app.command_window = console
