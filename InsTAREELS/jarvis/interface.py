"""Compact island controls connected to the existing Jarvis lifecycle."""
import os
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from .island import Island, KEY, BLACK
from .display import window_scale

BG = BLACK
CARD = '#121216'
LINE = '#2b2b32'
CYAN = '#b4a1ff'
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
    root.geometry(f'208x52+{(root.winfo_screenwidth()-208)//2}+12')
    app.island_canvas = tk.Canvas(root, width=208, height=52, bg=KEY, highlightthickness=0, cursor='hand2', takefocus=True)
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

    app.panel = tk.Toplevel(root)
    app.panel.withdraw()
    app.panel.title('Jarvis')
    app.panel.overrideredirect(True)
    app.panel.configure(bg=BG)
    app.panel.attributes('-topmost', True)
    try:
        opacity = min(1.,max(.8,float(app.config.get('ui',{}).get('opacity',.96))))
        root.attributes('-alpha',opacity)
        app.panel.attributes('-alpha',opacity)
    except (tk.TclError,TypeError,ValueError):
        pass
    app.panel.geometry('500x316+20000+20000')
    app.panel.protocol('WM_DELETE_WINDOW', app.hide_panel)
    app.panel.bind('<Escape>', lambda _event: app.hide_panel())

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TButton', font=('Segoe UI', 9), padding=(8, 5), background=LINE, foreground=TEXT,
                    borderwidth=0, focusthickness=1, focuscolor=CYAN)
    style.map('TButton', background=[('active', '#3a3a44'), ('pressed', '#484852')])
    style.configure('Accent.TButton', background=CYAN, foreground=BG, font=('Segoe UI', 9, 'bold'))
    style.map('Accent.TButton', background=[('active', '#d4c9ff'), ('pressed', '#9884e9')])
    style.configure('TCheckbutton', background=BG, foreground=TEXT, font=('Segoe UI', 9))
    style.configure('TEntry', fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT, padding=6)
    style.configure('TCombobox', fieldbackground=CARD, foreground=TEXT, background=LINE, arrowcolor=TEXT, padding=4)
    style.map('TCombobox', fieldbackground=[('readonly', CARD)], foreground=[('readonly', TEXT)])
    style.configure('Horizontal.TProgressbar', background='#8bdda8', troughcolor=LINE, borderwidth=0, thickness=2)
    root.option_add('*TCombobox*Listbox.background', CARD)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)

    shell = tk.Frame(app.panel, bg=BG)
    shell.pack(fill='both', expand=True)
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(3, weight=1)
    app.hud_status = tk.StringVar(value='STANDBY')
    app.ui_activity = ''
    app.state = tk.StringVar(value='Microphone off')
    app.live = tk.StringVar(value='Ready when you are.')
    app.question = tk.StringVar()
    header = tk.Frame(shell, bg=BG)
    header.grid(row=0, column=0, sticky='ew')
    app.state_label = label(header, textvariable=app.state, fg=MUTED, font=('Segoe UI', 9), anchor='w', wraplength=round(330*scale))
    app.state_label.pack(side='left', fill='x', expand=True)
    ttk.Button(header, text='Hide', command=app.hide_panel).pack(side='right')
    compact_reply = tk.StringVar(value=app.live.get())
    compact_question = tk.StringVar()
    def update_snippet(*_args):
        value = app.live.get()
        compact_reply.set(value[:150] + ('…' if len(value)>150 else ''))
        value = app.question.get()
        compact_question.set(value[:120] + ('…' if len(value)>120 else ''))
    app.live.trace_add('write', update_snippet)
    app.question.trace_add('write', update_snippet)
    app.reply_label = label(shell, textvariable=compact_reply, anchor='w', justify='left', wraplength=round(480*scale), font=('Segoe UI', 11))
    app.reply_label.grid(row=1, column=0, sticky='ew', pady=(7, 4))
    app.question_label = label(shell, textvariable=compact_question, fg='#f1c580', wraplength=round(480*scale), justify='left')
    app.question_label.grid(row=2, column=0, sticky='ew')

    body = tk.Frame(shell, bg=BG)
    body.grid(row=3, column=0, sticky='nsew', pady=6)
    from .island_desk import IslandDesk
    app.desk = IslandDesk(app,body)
    app.log = ScrolledText(app.desk.history, height=3, bg=CARD, fg=TEXT, insertbackground=TEXT, relief='flat',
                          borderwidth=0, padx=10, pady=8, font=('Segoe UI', 10), state='disabled', wrap='word')
    app.log.pack(fill='both', expand=True)
    app.log.vbar.configure(bg=LINE, troughcolor=BG, activebackground=CYAN, borderwidth=0)
    app.log.tag_configure('answer', foreground='#d5cbff')
    app.log.tag_configure('repair', foreground=MUTED)
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
    app.level = ttk.Progressbar(shell, maximum=100)
    app.level.grid(row=4, column=0, sticky='ew')
    app.preview = ttk.Entry(shell)
    app.preview.grid(row=5, column=0, sticky='ew', pady=(8,6))
    app.preview.bind('<Return>', lambda _event: app.send_input())
    controls = tk.Frame(shell, bg=BG)
    controls.grid(row=6, column=0, sticky='ew')
    for text, handler in (('Ask',app.ask_question),('Ask screen',app.ask_screen),('Do task',app.do_task)):
        ttk.Button(controls,text=text,command=handler,style='Accent.TButton' if text=='Ask' else 'TButton').pack(side='left',padx=(0,5))
    app.toggle = ttk.Button(controls,text='Start listening',command=app.toggle_listening)
    app.toggle.pack(side='right')
    footer = tk.Frame(shell,bg=BG)
    footer.grid(row=7,column=0,sticky='ew',pady=(6,0))
    for text,handler in (('Stop tasks',app.stop),('Stop voice',app.speech.cancel),('Settings',settings_toggle)):
        ttk.Button(footer,text=text,command=handler).pack(side='left',padx=(0,5))
    ttk.Button(footer,text='Quit Jarvis',command=app.close).pack(side='right')
    def resize(event):
        if event.widget == app.panel:
            app.reply_label.configure(wraplength=max(160,event.width-10))
            app.question_label.configure(wraplength=max(160,event.width-10))
    app.panel.bind('<Configure>',resize)
