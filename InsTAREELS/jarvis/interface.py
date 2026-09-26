"""Modern Tk Jarvis console, wired to the existing App actions and lifecycle."""
import os
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from PIL import ImageTk
from .hud import render_hud, logo_frames

BG = "#070f16"
CARD = "#0d1b27"
LINE = "#193545"
CYAN = "#48d9f3"
TEXT = "#dbeaf2"
MUTED = "#8da6b7"


def label(parent, text="", **kwargs):
    return tk.Label(parent, text=text, bg=kwargs.pop("bg", BG), fg=kwargs.pop("fg", TEXT),
                    font=kwargs.pop("font", ("Segoe UI", 10)), **kwargs)


def build_interface(app):
    root = app.root
    root.title("Jarvis HUD")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=BG)
    root.geometry(f"138x164+{(root.winfo_screenwidth()-138)//2}+12")
    app.orb = tk.Canvas(root, width=138, height=164, bg=BG, highlightthickness=1,
                        highlightbackground=LINE, cursor="hand2")
    app.orb.pack()
    drag = {"start": None, "moved": False}
    def press(event):
        drag.update(start=(event.x_root, event.y_root, root.winfo_x(), root.winfo_y()), moved=False)
    def move(event):
        if drag["start"] is None:
            return
        x, y, left, top = drag["start"]
        if abs(event.x_root-x) + abs(event.y_root-y) > 5:
            drag["moved"] = True
            left = max(0, min(root.winfo_screenwidth()-138, left+event.x_root-x))
            top = max(0, min(root.winfo_screenheight()-164, top+event.y_root-y))
            root.geometry(f"+{left}+{top}")
    def release(event):
        if not drag["moved"]:
            app.toggle_panel(event)
        drag["start"] = None
    app.orb.bind("<Button-1>", press)
    app.orb.bind("<B1-Motion>", move)
    app.orb.bind("<ButtonRelease-1>", release)
    app.orb.bind("<Button-3>", app.show_menu)
    app.menu = tk.Menu(root, tearoff=False, bg=CARD, fg=TEXT, activebackground=LINE, activeforeground=CYAN)
    for text, command in (("Open Jarvis", app.show_panel), ("Start / stop listening", app.toggle_listening),
                          ("Command prompt", app.show_command_prompt), ("Stop voice", app.speech.cancel)):
        app.menu.add_command(label=text, command=command)
    app.menu.add_separator()
    app.menu.add_command(label="Quit Jarvis", command=app.close)

    app.panel = tk.Toplevel(root)
    app.panel.withdraw()
    app.panel.title("J.A.R.V.I.S. · Command center")
    app.panel.configure(bg=BG)
    app.panel.attributes("-topmost", True)
    width = min(900, root.winfo_screenwidth()-40)
    height = min(780, root.winfo_screenheight()-80)
    app.panel.geometry(f"{width}x{height}+{max(0,(root.winfo_screenwidth()-width)//2)}+{max(10,min(184,root.winfo_screenheight()-height-32))}")
    app.panel.minsize(min(660, width), min(620, height))
    app.panel.protocol("WM_DELETE_WINDOW", app.hide_panel)
    app.panel.bind("<Escape>", lambda _event: app.hide_panel())

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8), background=LINE, foreground=TEXT,
                    borderwidth=0, focusthickness=1, focuscolor=CYAN)
    style.map("TButton", background=[("active", "#245069"), ("pressed", "#29647d")])
    style.configure("Accent.TButton", background=CYAN, foreground=BG, font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#9ceeff"), ("pressed", "#25aec8")])
    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    style.map("TCheckbutton", background=[("active", BG)], foreground=[("active", CYAN)])
    style.configure("TEntry", fieldbackground=CARD, foreground=TEXT, insertcolor=CYAN, padding=8)
    style.configure("TCombobox", fieldbackground=CARD, foreground=TEXT, background=LINE, arrowcolor=CYAN, padding=6)
    style.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", TEXT)])
    style.configure("Horizontal.TProgressbar", background=CYAN, troughcolor=LINE, borderwidth=0, thickness=3)
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=CARD, foreground=MUTED, padding=(16, 9))
    style.map("TNotebook.Tab", background=[("selected", LINE)], foreground=[("selected", CYAN)])
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)

    shell = tk.Frame(app.panel, bg=BG, padx=24, pady=18)
    shell.pack(fill="both", expand=True)
    shell.grid_columnconfigure(0, weight=1)
    shell.grid_rowconfigure(5, weight=1)
    header = tk.Frame(shell, bg=BG)
    header.grid(row=0, column=0, sticky="ew")
    label(header, "J.A.R.V.I.S.", fg=CYAN, font=("Segoe UI", 23, "bold")).pack(side="left")
    label(header, "PERSONAL ASSISTANT", fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=18)
    ttk.Button(header, text="Hide", command=app.hide_panel).pack(side="right")
    tk.Frame(shell, bg=LINE, height=1).grid(row=1, column=0, sticky="ew", pady=(12, 16))

    hero = tk.Frame(shell, bg=BG)
    hero.grid(row=2, column=0, sticky="ew")
    app.hud_size = min(180, max(110, (height-380)//2))
    app.panel_photo = ImageTk.PhotoImage(render_hud(size=app.hud_size), master=root)
    app.panel_logo = tk.Label(hero, bg=BG, cursor="hand2", image=app.panel_photo)
    app.panel_logo.pack(side="left", padx=(0, 22))
    app.panel_logo.bind("<Button-1>", lambda _event: app.toggle_listening())
    status = tk.Frame(hero, bg=BG)
    status.pack(side="left", fill="both", expand=True)
    app.hud_status = tk.StringVar(value="STANDBY")
    app.ui_activity = ""
    label(status, textvariable=app.hud_status, fg=CYAN, font=("Consolas", 10, "bold")).pack(anchor="w", pady=(10, 6))
    app.state = tk.StringVar(value="Microphone off")
    app.state_label = label(status, textvariable=app.state, font=("Segoe UI", 15), wraplength=max(220,width-310), justify="left")
    app.state_label.pack(anchor="w")
    app.live = tk.StringVar(value="Ready when you are. Ask a question or give me a task.")
    app.reply_label = label(status, textvariable=app.live, bg=CARD, justify="left", anchor="nw",
                            wraplength=max(220,width-310), height=3, padx=14, pady=12, font=("Segoe UI", 11))
    app.reply_label.pack(fill="x", pady=(12, 8))
    app.level = ttk.Progressbar(status, maximum=100)
    app.level.pack(fill="x", pady=(2, 10))
    app.question = tk.StringVar()
    label(shell, textvariable=app.question, fg=CYAN, wraplength=width-70, justify="left").grid(row=3, column=0, sticky="ew", pady=4)

    controls = tk.Frame(shell, bg=BG)
    controls.grid(row=4, column=0, sticky="ew", pady=(8, 14))
    app.toggle = ttk.Button(controls, text="Start listening", style="Accent.TButton", command=app.toggle_listening)
    app.toggle.pack(side="left")
    ttk.Button(controls, text="Stop tasks", command=app.stop).pack(side="left", padx=8)
    app.speak_enabled = tk.BooleanVar(value=app.speech.options.get("enabled", True))
    ttk.Checkbutton(controls, text="Speak replies", variable=app.speak_enabled, command=app.save_speech_settings).pack(side="left", padx=6)
    ttk.Button(controls, text="Stop voice", command=app.speech.cancel).pack(side="right")

    notebook = ttk.Notebook(shell)
    notebook.grid(row=5, column=0, sticky="nsew")
    conversation = tk.Frame(notebook, bg=BG, pady=10)
    settings = tk.Frame(notebook, bg=BG, padx=12, pady=14)
    notebook.add(conversation, text="Conversation")
    notebook.add(settings, text="Voice & settings")
    app.log = ScrolledText(conversation, height=6, bg=CARD, fg=TEXT, insertbackground=CYAN,
                          relief="flat", borderwidth=0, padx=14, pady=12, font=("Consolas", 10), state="disabled")
    app.log.pack(fill="both", expand=True)
    app.log.vbar.configure(bg=LINE, troughcolor=BG, activebackground=CYAN, borderwidth=0)
    app.log.tag_configure("answer", foreground="#b8f5ff")
    app.log.tag_configure("repair", foreground=MUTED)
    input_bar = tk.Frame(settings, bg=BG)
    input_bar.pack(fill="x", pady=(0, 16))
    label(input_bar, "Microphone", fg=MUTED, width=16, anchor="w").pack(side="left")
    app.mic_choice = ttk.Combobox(input_bar, state="readonly", width=40)
    app.mic_choice.pack(side="left", fill="x", expand=True)
    app.mic_devices = [None]
    app.mic_choice["values"] = ["System default microphone"]
    app.mic_choice.current(0)
    languages = tk.Frame(settings, bg=BG)
    languages.pack(fill="x", pady=(0, 16))
    label(languages, "Reply language", fg=MUTED, width=16, anchor="w").pack(side="left")
    app.answer_language = ttk.Combobox(languages, state="readonly", width=16, values=["Auto", "English", "Hindi"])
    app.answer_language.pack(side="left")
    app.answer_language.set({"auto": "Auto", "en": "English", "hi": "Hindi"}.get(app.config.get("knowledge", {}).get("answer_language", "auto"), "Auto"))
    app.answer_language.bind("<<ComboboxSelected>>", app.save_speech_settings)
    app.backend = tk.StringVar(value=f"Whisper {app.config['whisper']['model']} · microphone initializes when listening starts")
    label(settings, textvariable=app.backend, fg=MUTED, wraplength=width-90, justify="left").pack(anchor="w")
    label(settings, "Your assistant runs locally. Repairs appear quietly in the conversation.", fg=MUTED).pack(anchor="w", pady=12)

    composer = tk.Frame(shell, bg=BG)
    composer.grid(row=6, column=0, sticky="ew", pady=(12, 0))
    app.preview = ttk.Entry(composer)
    app.preview.pack(side="left", fill="x", expand=True)
    app.preview.bind("<Return>", lambda _event: app.send_input())
    ttk.Button(composer, text="Ask", style="Accent.TButton", command=app.ask_question).pack(side="left", padx=(8, 0))
    ttk.Button(composer, text="Ask screen", command=app.ask_screen).pack(side="left", padx=(8, 0))
    ttk.Button(composer, text="Do task", command=app.do_task).pack(side="left", padx=(8, 0))
    footer = tk.Frame(shell, bg=BG)
    footer.grid(row=7, column=0, sticky="ew", pady=(10, 0))
    for text, command in (("Terminal", app.show_command_prompt), ("Preview", app.preview_command),
                          ("Files", lambda: os.startfile(app.actions.root))):
        ttk.Button(footer, text=text, command=command).pack(side="left", padx=(0, 8))
    ttk.Button(footer, text="Quit Jarvis", command=app.close).pack(side="right")
    def resize(event):
        if event.widget == app.panel:
            for widget in (app.reply_label, app.state_label):
                widget.configure(wraplength=max(220, event.width-310))
    app.panel.bind("<Configure>", resize)
    if not logo_frames(int(app.hud_size*.84)):
        app.report("repair", "Jarvis HUD artwork is unavailable; the built-in status emblem is being used.")
