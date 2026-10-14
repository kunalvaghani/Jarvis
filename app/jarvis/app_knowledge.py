"""What Jarvis knows about the apps on this PC: what each does, its main features, and the buttons it has.

Three layers:
- PROFILES: hand-written knowledge for the apps installed here (built from the 333 Start-menu apps in
  config "apps"): what the app does, its features, and the one question Jarvis offers when you're in it.
- inventory(): every configured app, matched to a profile or given a category from its name and executable.
- AppKnowledge: buttons, menus and tabs learned live through Windows UI Automation each time an app is in
  front (names only: never field values, list contents, chats, passwords or coordinates), saved to
  .jarvis-runtime/app_knowledge.json so Jarvis gets to know an app better the more you use it.
"""
import json
import re
import threading
import time
from pathlib import Path

BROWSERS = r"chrome|msedge|opera|firefox|brave|vivaldi"

# Offer modes (what a "yes" does):
#   video    - read the video titles on screen and open the one you name by a word from its title
#   dictate  - put the cursor in the app and type everything you say until "stop writing"
#   screen   - answer a question about what's on screen (prompt) with the screen model
#   ask      - you ask your own question about the screen; Jarvis answers looking at it
#   command  - your follow-up is turned into a normal Jarvis command with template
#   click    - your follow-up names something on screen; Jarvis finds it and presses it
#   calc     - work out the sum and type it into the calculator
#   run      - run a fixed Jarvis command
PROFILES = [
    dict(key="youtube", exe=BROWSERS, title=r"\bYouTube\b", name="YouTube", category="video",
         does="Video site: watch, search and browse videos, playlists and channels.",
         features=["search videos", "play / pause", "full screen", "captions", "like / subscribe", "recommended videos"],
         question="You're on YouTube. Want me to open one of the videos on screen? Just say a word from its title.",
         mode="video", followup="Which one? Say a word from its title."),
    dict(key="gmail", exe=BROWSERS, title=r"\b(?:Gmail|Inbox)\b", name="Gmail", category="email", private=True,
         does="Email in the browser: read, reply, search and send mail.",
         features=["compose", "reply", "search mail", "labels", "archive"],
         question="", mode=""),  # Mail is private: no unprompted questions.
    dict(key="ai_chat_web", exe=BROWSERS, title=r"\b(?:ChatGPT|Claude|Gemini|Copilot)\b", name="AI chat", category="ai",
         does="AI assistant in the browser: type a prompt and get an answer.",
         features=["new chat", "prompt box", "attach files", "chat history"],
         question="Do you want to dictate a prompt? Say yes and I'll type what you say.", mode="dictate"),
    dict(key="browser", exe=BROWSERS, name="Web browser", category="browser",
         does="Web browser: open sites, search the web, tabs, bookmarks, downloads and extensions.",
         features=["address bar", "tabs", "back / forward / reload", "bookmarks", "downloads", "extensions", "find in page"],
         question="Want a quick summary of this page?", mode="screen",
         prompt="Summarise the main content of this web page in three or four short sentences."),
    dict(key="notepad", exe=r"notepad|notepad\+\+", name="Notepad", category="notes",
         does="Plain-text editor for notes and text files.",
         features=["type text", "save / save as", "find and replace", "tabs", "word wrap"],
         question="Do you have something in mind to write? You can dictate and I'll write it.", mode="dictate"),
    dict(key="sticky_notes", exe=r"microsoft\.notes|stickynot|stickynotes", title=r"Sticky Notes", name="Sticky Notes", category="notes",
         does="Quick desktop notes.", features=["new note", "type text", "formatting", "note list"],
         question="Do you have something in mind to write? You can dictate and I'll write it.", mode="dictate"),
    dict(key="onenote", exe=r"onenote|onenoteim", name="OneNote", category="notes",
         does="Notebooks with sections and pages for notes.", features=["new page", "type notes", "lists", "drawings", "search"],
         question="Do you have something in mind to write? You can dictate and I'll write it.", mode="dictate"),
    dict(key="obsidian", exe=r"obsidian", name="Obsidian", category="notes",
         does="Markdown notes vault (Jarvis's long-term memory lives here too).",
         features=["new note", "links", "search", "graph view", "daily notes"],
         question="Do you have something in mind to write? You can dictate and I'll write it.", mode="dictate"),
    dict(key="word", exe=r"winword", name="Word", category="documents",
         does="Word processor for documents, letters and reports.",
         features=["type text", "styles", "insert tables and pictures", "spelling", "save / export PDF"],
         question="Do you have something in mind to write? You can dictate and I'll write it.", mode="dictate"),
    dict(key="excel", exe=r"excel", name="Excel", category="documents",
         does="Spreadsheets: tables, formulas and charts.", features=["cells and formulas", "charts", "sort / filter", "pivot tables"],
         question="Want me to explain this sheet or help with a formula?", mode="ask",
         followup="Go ahead, what do you want to know about the sheet?"),
    dict(key="powerpoint", exe=r"powerpnt", name="PowerPoint", category="documents",
         does="Slide presentations.", features=["new slide", "layouts", "designer", "slideshow"],
         question="Want me to suggest what to put on this slide?", mode="screen",
         prompt="Look at the slide on screen and suggest a title and three concise bullet points to improve it."),
    dict(key="ai_chat_app", exe=r"chatgpt|claude|copilot|cluely", name="AI chat app", category="ai",
         does="AI assistant app: type a prompt and get an answer.", features=["new chat", "prompt box", "attach files"],
         question="Do you want to dictate a prompt? Say yes and I'll type what you say.", mode="dictate"),
    dict(key="code_editor", exe=r"code|cursor|devenv|pycharm64|idea64|sublime_text", name="Code editor", category="code",
         does="Code editor / IDE: edit, run and debug code.",
         features=["explorer", "search", "source control", "run and debug", "terminal", "extensions"],
         question="Want me to explain the code on screen or look for a bug in it?", mode="screen",
         prompt="Explain briefly what the code visible in this editor does and point out any likely bug."),
    dict(key="terminal", exe=r"windowsterminal|cmd|powershell|pwsh|mintty|wt", name="Terminal", category="terminal",
         does="Command line: run commands and scripts.", features=["run commands", "tabs", "copy output"],
         question="Want me to explain the output or error on screen?", mode="screen",
         prompt="Explain the most recent command output or error visible in this terminal, and how to fix it if it's an error."),
    dict(key="explorer", exe=r"explorer", window_class=r"CabinetWClass|ExploreWClass", name="File Explorer", category="files",
         does="Browse, open, copy, move and rename files and folders.",
         features=["navigation pane", "address bar", "search", "new folder", "copy / paste", "sort and view"],
         question="Looking for a file or folder here? Say its name and I'll open it.", mode="click",
         followup="Which one? Say its name.", roles=["ListItem", "TreeItem", "DataItem"], verb="open"),
    dict(key="spotify", exe=r"spotify", name="Spotify", category="music",
         does="Music streaming: songs, albums, playlists and podcasts.",
         features=["search", "play / pause / skip", "playlists", "liked songs", "volume", "queue"],
         question="Want me to play something? Say yes, then the song or artist.", mode="command",
         followup="What should I play?", template="play {x} on spotify"),
    dict(key="media_player", exe=r"vlc|wmplayer|microsoft\.media\.player|zunemusic|zunevideo", name="Media player", category="media",
         does="Plays local music and video files.", features=["play / pause", "next / previous", "volume", "full screen", "playlist"],
         question="Want me to pause, skip or change something in the player? Say yes, then the button.", mode="click",
         followup="Which button? For example pause, next or full screen.", roles=["Button", "SplitButton", "Slider"]),
    dict(key="whatsapp", exe=r"whatsapp", name="WhatsApp", category="messaging", private=True,
         does="Messaging: chats, voice and video calls.", features=["chats", "new message", "calls", "status", "search"],
         question="Want to message someone? Say yes, then who and what to say.", mode="command",
         followup="Who should I message, and what should it say?", template="message {x} on whatsapp", app="whatsapp"),
    dict(key="telegram", exe=r"telegram", name="Telegram", category="messaging", private=True,
         does="Messaging: chats, groups and channels.", features=["chats", "search", "groups", "channels"],
         question="Want to message someone? Say yes, then who and what to say.", mode="command",
         followup="Who should I message, and what should it say?", template="message {x} on telegram", app="telegram"),
    dict(key="discord", exe=r"discord", name="Discord", category="messaging", private=True,
         does="Chat and voice for communities and friends.", features=["servers", "channels", "direct messages", "voice"],
         question="Want to message someone? Say yes, then who and what to say.", mode="command",
         followup="Who should I message, and what should it say?", template="message {x} on discord", app="discord"),
    dict(key="teams", exe=r"ms-teams|teams", name="Microsoft Teams", category="messaging", private=True,
         does="Work chat, meetings and calls.", features=["chat", "teams and channels", "calendar", "meetings"],
         question="Want to message someone? Say yes, then who and what to say.", mode="command",
         followup="Who should I message, and what should it say?", template="message {x} on teams", app="teams"),
    dict(key="zoom", exe=r"zoom", name="Zoom", category="meetings", does="Video meetings.",
         features=["join", "mute / unmute", "video on / off", "share screen", "chat"],
         question="Want me to press something in Zoom? Say yes, then the button, like mute or share screen.", mode="click",
         followup="Which button?", roles=["Button", "SplitButton"]),
    dict(key="outlook", exe=r"olk|outlook", name="Outlook", category="email", private=True,
         does="Email and calendar.", features=["inbox", "new mail", "reply", "calendar", "search"], question="", mode=""),
    dict(key="calculator", exe=r"calculatorapp|calc", title=r"Calculator", name="Calculator", category="tools",
         does="Calculator: standard, scientific, programmer and converters.",
         features=["standard", "scientific", "history", "unit converter"],
         question="Want me to calculate something? Say yes, then the sum.", mode="calc", followup="What should I calculate?"),
    dict(key="settings", exe=r"systemsettings", title=r"Settings", name="Settings", category="system",
         does="Windows settings: display, sound, Bluetooth, network, apps, privacy and updates.",
         features=["search settings", "system", "Bluetooth & devices", "network", "personalisation", "Windows Update"],
         question="Which setting are you looking for? Say yes, then the setting.", mode="command",
         followup="Which setting?", template="open {x} settings"),
    dict(key="task_manager", exe=r"taskmgr", name="Task Manager", category="system",
         does="Running apps and processes, CPU, memory, disk and startup apps.",
         features=["processes", "performance", "startup apps", "end task"],
         question="Want me to tell you what's using the most CPU and memory?", mode="run", run="what is using the most cpu"),
    dict(key="paint", exe=r"mspaint", name="Paint", category="creative", does="Simple drawing and image editing.",
         features=["brushes", "shapes", "text", "crop / resize", "layers"],
         question="Want me to pick a tool in Paint? Say yes, then the tool.", mode="click", followup="Which tool?",
         roles=["Button", "SplitButton", "ListItem", "RadioButton"]),
    dict(key="photos", exe=r"photos", name="Photos", category="media", does="View and edit photos and videos.",
         features=["next / previous", "edit", "rotate", "slideshow"],
         question="Want me to press something in Photos? Say yes, then the button.", mode="click", followup="Which button?",
         roles=["Button", "SplitButton"]),
    dict(key="game_launcher", exe=r"steam|steamwebhelper|epicgameslauncher|eadesktop|ealauncher|xboxpcapp|tlauncher", name="Game launcher",
         category="games", does="Your game library: install, update and launch games.", features=["library", "store", "friends", "downloads"],
         question="Want to open one of your games? Say yes, then its name.", mode="click", followup="Which game?",
         roles=["Hyperlink", "ListItem", "Button", "TreeItem"]),
    dict(key="obs", exe=r"obs64", name="OBS Studio", category="creative", does="Screen recording and live streaming.",
         features=["start / stop recording", "start streaming", "scenes", "sources", "audio mixer"],
         question="Want me to press something in OBS? Say yes, then the button, like start recording.", mode="click",
         followup="Which button?", roles=["Button", "CheckBox"]),
    dict(key="creative_3d", exe=r"blender|unity|unity hub|unrealeditor|gaea|tiled", name="3D / game editor", category="creative",
         does="3D modelling, terrain or game development.", features=["viewport", "scene / outliner", "properties", "render / play"],
         question="Need help with what's on screen? Say yes and ask me how to do something.", mode="ask",
         followup="Go ahead, what do you want to do?"),
    dict(key="git_client", exe=r"githubdesktop|sourcetree|git-gui", name="Git client", category="code",
         does="Commit, branch, pull and push code repositories.", features=["changes", "commit", "history", "branches", "push / pull"],
         question="Want me to summarise the changes on screen?", mode="screen",
         prompt="Summarise the code changes visible in this Git client in a few short sentences."),
    dict(key="docker", exe=r"docker desktop", name="Docker Desktop", category="code", does="Containers, images and volumes.",
         features=["containers", "images", "volumes", "logs"],
         question="Want me to explain what's on screen?", mode="screen", prompt="Explain the containers or logs visible on screen and anything that looks wrong."),
    dict(key="security", exe=r"sechealthui|malwarebytes|mcuicnt", name="Security app", category="security",
         does="Antivirus and device security.", features=["scan", "protection status", "firewall", "history"],
         question="Want me to explain the security status on screen?", mode="screen",
         prompt="Explain the security status shown on screen and whether anything needs attention."),
]
for _profile in PROFILES:
    _profile.setdefault("private", False)

# Category from the app's name or executable, for apps without a profile.
CATEGORY_WORDS = [
    ("video", r"\byou ?tube\b"),
    ("files", r"\b(?:file explorer|file manager|files|7z fm)\b"),
    ("documents", r"\b(?:msaccess|mspub|msoxmled|msoasb|msoadfsb|sdxhelper|skypeserver|office language preferences|telemetry log for office)\b"),
    ("email", r"\b(?:relay cold email assistant|wab|wabmig)\b"),
    ("system", r"\b(?:magnif\w*|i scsi initiator|memory diagnostics tool|steps recorder|tab tip|translucent tb|hyper x ngenuity|"
               r"b o audio control|global flags \w+|application verifier \w+|gpuview|dfrgui|mixed reality portal|power automate|"
               r"intel unison|windows fax and scan|licensemanagershellext|windows package manager server|windows app cert kit|"
               r"windows software development kit|tools for desktop apps|family|get started|check for updates|oracle virtual box|"
               r"shell mcp servers.packaging|start rlcms|ms-teamsupdate|spotify_cli|pythonw.exe|javaws|iediag\w*|"
               r"microsoft silverlight|microsoft azure compute emulator.*)\b"),
    ("help", r"\b(?:help|manual|documentation|dokumentation|faq|frequently asked|release notes|read me|license|what is new|samples|homepage|website|visit)\b"),
    ("uninstaller", r"\buninstall"),
    ("browser", r"\b(?:chrome|edge|opera|firefox|tor browser|iexplore)\b"),
    ("notes", r"\b(?:notepad|note|sticky|obsidian|journal)\b"),
    ("documents", r"\b(?:word|excel|power ?point|publisher|access|acrobat|xps|spreadsheet)\b"),
    ("code", r"\b(?:code|cursor|visual studio|devenv|python|idle|node|git|cmake|erlang|java|sdk|docker|vulkan|windbg|debug|sourcetree|wsl)\b"),
    ("terminal", r"\b(?:command prompt|power ?shell|terminal|cmd|bash|console)\b"),
    ("music", r"\b(?:spotify|soundly|music)\b"),
    ("media", r"\b(?:vlc|media player|films|photos|camera|clipchamp|sound recorder|wmplayer|prime video|3d viewer)\b"),
    ("messaging", r"\b(?:whats ?app|telegram|discord|teams|skype|lync|zoom|phone link|people)\b"),
    ("email", r"\b(?:outlook|mail|olk)\b"),
    ("games", r"\b(?:steam|epic|ea|xbox|game|solitaire|counter-strike|tlauncher|geforce now|omen)\b"),
    ("creative", r"\b(?:paint|blender|unity|unreal|gaea|tiled|obs|phaser|whiteboard|snipping)\b"),
    ("security", r"\b(?:security|defender|firewall|malwarebytes|mc ?afee)\b"),
    ("cloud", r"\b(?:drive|dropbox|one ?drive|backup)\b"),
    ("ai", r"\b(?:chat gpt|claude|copilot|cluely|ollama)\b"),
    ("system", r"\b(?:settings|control panel|task manager|services|registry|event viewer|disk|defragment|computer management|"
               r"system|performance|resource monitor|magnif|narrator|keyboard|recovery|diagnostic|scheduler|odbc|component|"
               r"administrative|run|windows tools|nvidia|amd|hp|power toys|wireless display|voice access|live captions)\b"),
    ("tools", r"\b(?:calculator|clock|calendar|maps|weather|character map|7-zip|rar|to do|store|winget|news|get help|quick assist|feedback)\b"),
]
CATEGORY_TEXT = {"help": "help pages and documentation", "uninstaller": "uninstallers", "browser": "web browsers",
                 "notes": "notes", "documents": "documents and office", "code": "coding and developer tools",
                 "terminal": "terminals", "music": "music", "media": "photos, video and media", "messaging": "messaging and calls",
                 "email": "email", "games": "games and launchers", "creative": "creative, 3D and recording",
                 "security": "security", "cloud": "cloud storage and backup", "ai": "AI assistants", "system": "Windows and hardware tools",
                 "tools": "everyday tools", "other": "other apps", "video": "video", "files": "files", "meetings": "meetings"}
KEEP_ROLES = {"Button", "SplitButton", "MenuItem", "TabItem", "CheckBox", "RadioButton", "ComboBox"}
PRIVATE_LABEL = re.compile(r"@|\d{4,}|https?:|\bunread\b|\bnew notifications?\b|\(\d+\)|\bminutes?\b.*\bseconds?\b", re.I)
PRIVATE_TITLE = re.compile(r"(?i)\b(?:incognito|inprivate|private browsing|bank|banking|password|sign in|log ?in|checkout|payment)\b")


def _exe_name(executable):
    return Path(str(executable or "")).stem.casefold()


def profile_for(executable="", title="", window_class=""):
    """The best profile for a window (title-specific profiles such as YouTube win over the plain browser)."""
    exe = _exe_name(executable)
    for profile in PROFILES:
        if not re.fullmatch("(?:" + profile["exe"] + ")", exe):
            continue
        if profile.get("title") and not re.search(profile["title"], title or ""):
            continue
        if profile.get("window_class") and window_class and not re.fullmatch(profile["window_class"], window_class):
            continue
        return profile
    return None


def category_of(name, executable="", entry=""):
    if "steam://" in entry:
        return "games"
    text = (name + " " + _exe_name(executable)).casefold()
    profile = profile_for(executable) if executable else None
    if profile and not profile.get("title"):
        return profile["category"]
    for category, pattern in CATEGORY_WORDS:
        if re.search(pattern, text):
            return category
    return "other"


def _executable(entry):
    text = json.dumps(entry)
    found = re.findall(r"[^\\/\"]+\.exe", text, re.I)
    return found[-1] if found else ""


def inventory(apps):
    """Every configured app with its category, executable and, when there is one, its profile."""
    rows = []
    for name, entry in sorted((apps or {}).items()):
        exe = _executable(entry)
        profile = profile_for(exe) if exe else None
        if profile is None:
            profile = next((p for p in PROFILES if not p.get("title") and re.search(r"\b(?:" + p["exe"] + r")\b", name.replace(" ", ""), re.I)), None)
        rows.append({"name": name, "exe": exe, "category": profile["category"] if profile and not profile.get("title") else category_of(name, exe, json.dumps(entry)),
                     "profile": profile["key"] if profile and not profile.get("title") else None})
    return rows


class AppKnowledge:
    """Profiles plus buttons learned live, per app."""
    def __init__(self, base, apps=None):
        self.path = Path(base) / ".jarvis-runtime" / "app_knowledge.json"
        self.apps = apps or {}
        self.lock = threading.Lock()
        try:
            self.learned = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.learned, dict):
                self.learned = {}
        except (OSError, ValueError):
            self.learned = {}
        self._inventory = None

    def inventory(self):
        if self._inventory is None:
            self._inventory = inventory(self.apps)
        return self._inventory

    def capabilities(self, identity, feature='', ttl=604800, version=None, signature=None):
        """Bounded version/surface-aware retrieval from this existing app store."""
        with self.lock:
            row = self.learned.get('capability:'+identity, {})
            if not isinstance(row, dict):
                return []
            result = []
            records = row.get('capabilities', {})
            if not isinstance(records, dict):
                return []
            for item in list(records.values())[:24]:
                if (not isinstance(item, dict) or not isinstance(item.get('seen_at'), (int, float)) or
                        not all(k in item for k in ('identity','feature','version','status','interface_signature','controls','sources','verification')) or
                        not all(isinstance(item[k], list) for k in ('controls','sources','verification')) or
                        not 0 <= time.time()-item['seen_at'] <= ttl):
                    continue
                if (feature and item.get('feature') != feature or version and version != 'unknown' and item.get('version') != version or
                        signature and item.get('interface_signature') != signature or item.get('status') == 'invalidated'):
                    continue
                result.append(json.loads(json.dumps(item)))
            return sorted(result, key=lambda item: item['seen_at'], reverse=True)[:3]

    def remember_capability(self, item):
        """Persist declarative evidence, never code, coordinates or permissions."""
        required = {'identity','feature','version','interface_signature','controls','sources','status','tools',
                    'verification','seen_at','executions'}
        if not isinstance(item, dict) or set(item) != required or len(json.dumps(item, ensure_ascii=False)) > 18000:
            raise ValueError('Invalid bounded capability record.')
        if (item['status'] not in {'discovered','researched','environment_confirmed','verified','invalidated'} or
                not all(isinstance(item[k], str) and 0 < len(item[k]) <= 300 for k in ('identity','feature','version')) or
                not isinstance(item['controls'], list) or len(item['controls']) > 60 or
                not isinstance(item['sources'], list) or len(item['sources']) > 3 or
                item['status'] == 'verified' and not item['verification']):
            raise ValueError('Capability status requires real evidence.')
        from .skill_memory import linked
        if linked(self.path) or linked(self.path.parent):
            raise ValueError('App knowledge paths cannot be linked.')
        key = 'capability:'+item['identity']
        with self.lock:
            row = self.learned.setdefault(key, {'buttons': {}, 'capabilities': {}})
            old = row.setdefault('capabilities', {}).get(item['feature'])
            if old and item['status'] != 'verified' and old.get('version') == item['version'] and old.get('interface_signature') == item['interface_signature'] and old.get('status') == 'verified':
                item = {**item, 'status': 'verified', 'executions': old['executions'], 'verification': old['verification']}
            row['capabilities'][item['feature']] = json.loads(json.dumps(item))
            row['capabilities'] = dict(sorted(row['capabilities'].items(), key=lambda pair: pair[1]['seen_at'], reverse=True)[:24])
            capability_keys = [k for k in self.learned if k.startswith('capability:')]
            if len(capability_keys) > 64:
                oldest = min(capability_keys, key=lambda k: max((r.get('seen_at', 0) for r in self.learned[k]['capabilities'].values()), default=0))
                self.learned.pop(oldest)
            if not self._save():
                raise OSError('Capability persistence failed.')

    def acquired_context(self, goal):
        """Semantic guidance only; similarity never authorizes action reuse."""
        tokens = set(re.findall(r'[a-z]+', goal.casefold()))
        result = []
        for key in list(self.learned)[:1000]:
            if key.startswith('capability:'):
                for row in self.capabilities(key[len('capability:'):]):
                    if tokens & set(re.findall(r'[a-z]+', row['feature']+' '+row['identity'])):
                        result.append({k: row[k] for k in ('identity','feature','version','status','interface_signature')})
                        result[-1]['controls'] = row['controls'][:8]
                        result[-1]['sources'] = [{'url': s['url'], 'excerpt': s.get('excerpt','')[:300]} for s in row['sources'][:2]]
                        result[-1]['verification'] = row['verification'][:1]
        return result[:3]

    def refresh_capability_sources(self, identity, feature, sources):
        """Background docs refresh cannot extend stale UI/workflow verification."""
        from .skill_memory import linked
        if linked(self.path) or linked(self.path.parent):
            raise ValueError('App knowledge paths cannot be linked.')
        with self.lock:
            row = self.learned.get('capability:'+identity, {}).get('capabilities', {}).get(feature)
            if row is not None:
                row['sources'] = json.loads(json.dumps(sources[:3]))
                if not self._save():
                    raise OSError('Capability source persistence failed.')

    @staticmethod
    def app_key(executable, title="", window_class=""):
        profile = profile_for(executable, title, window_class)
        return profile["key"] if profile else (_exe_name(executable) or "unknown")

    def learn(self, executable, title, controls, window_class=""):
        """Remember the names of buttons, menus and tabs this app shows (never values or list contents)."""
        key = self.app_key(executable, title, window_class)
        names = [c["name"].strip().splitlines()[0][:60] for c in controls if c.get("role") in KEEP_ROLES and c.get("name", "").strip()
                 and not c.get("password") and not PRIVATE_LABEL.search(c["name"]) and len(c["name"].strip()) > 1]
        if not names:
            return 0
        with self.lock:
            row = self.learned.setdefault(key, {"exe": _exe_name(executable), "buttons": {}, "seen": 0})
            row["seen"] += 1
            row["last_seen"] = time.strftime("%Y-%m-%d %H:%M")
            for name in names:
                row["buttons"][name] = row["buttons"].get(name, 0) + 1
            if len(row["buttons"]) > 150:  # Keep the ones seen most often.
                row["buttons"] = dict(sorted(row["buttons"].items(), key=lambda kv: -kv[1])[:150])
            self._save()
        return len(names)

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.learned, ensure_ascii=False, indent=1), encoding="utf-8")
            temp.replace(self.path)
            return True
        except OSError:
            return False

    def buttons(self, key, limit=20):
        row = self.learned.get(key) or {}
        skip = {"close", "minimize", "maximize", "restore", "system", "minimise", "maximise"}
        return [name for name, _ in sorted(row.get("buttons", {}).items(), key=lambda kv: -kv[1]) if name.casefold() not in skip][:limit]

    def describe(self, executable, title="", window_class=""):
        """What Jarvis knows about the app in front: for the live context and 'what can you do here'."""
        profile = profile_for(executable, title, window_class)
        key = self.app_key(executable, title, window_class)
        entry = {"app": profile["name"] if profile else (_exe_name(executable) or "this app"),
                 "category": profile["category"] if profile else category_of(_exe_name(executable), executable)}
        if profile:
            entry["does"] = profile["does"]
            entry["features"] = profile["features"]
        known = self.buttons(key, 15)
        if known:
            entry["buttons_seen"] = known
        return entry

    def summary(self):
        rows = [r for r in self.inventory() if r["category"] not in {"help", "uninstaller"}]
        groups = {}
        for row in rows:
            groups.setdefault(row["category"], []).append(row["name"])
        order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
        parts = [f"{len(names)} {CATEGORY_TEXT.get(cat, cat)}, like {', '.join(sorted(set(names), key=len)[:3])}"
                 for cat, names in order]
        learned = sum(1 for row in self.learned.values() if row.get("buttons"))
        return (f"You have {len(rows)} apps I can open, not counting help pages and uninstallers: " + "; ".join(parts) +
                f". I know what {len([p for p in PROFILES if p['question'] or p['private']])} kinds of app do, and I've learned "
                f"the buttons of {learned} app{'s' if learned != 1 else ''} so far by watching them on screen.")

    def explain_current(self, executable, title="", window_class=""):
        info = self.describe(executable, title, window_class)
        profile = profile_for(executable, title, window_class)
        text = f"This is {info['app']}. " + (info.get("does", "") + " " if info.get("does") else "")
        if info.get("features"):
            text += "Main features: " + ", ".join(info["features"]) + ". "
        if info.get("buttons_seen"):
            text += "Buttons I've seen here: " + ", ".join(info["buttons_seen"][:12]) + ". "
        else:
            text += "I haven't learned this app's buttons yet; I pick them up while it's in front. "
        if profile and profile.get("question"):
            text += "I can help here: " + profile["question"].split("?")[0].rstrip(".") + "?"
        return text.strip()
