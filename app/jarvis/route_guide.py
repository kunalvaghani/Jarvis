"""Which channel fits each job: APIs, code and MCP first, structured screen control next, vision last.

Planner context only (capabilities.runtime_context -> execution_strategy.hint): it never dispatches. For every app
or target the request names it gives an ordered list of the tools that can do the work, filtered to the tools
offered in this task, plus two rules:

- When the user explicitly asks for an app's own interface ("open Notepad and type", "use the Calculator app"),
  the work happens in that app on screen; APIs may only read or verify.
- Screen awareness: after an API/code method changes something the user can see, open it in its app so the
  user sees the result, and read it back to verify.
"""
import re

APPS = 'notepad|calculator|paint|excel|word|blender|vs ?code|visual studio code|obsidian|explorer|file explorer'
EXPLICIT = re.compile(rf'\b(?:open|launch|start|use|using|in|with|inside)\s+(?:the\s+)?(?:{APPS})\b(?:\s+app)?.*?'
                      r'\b(?:type|write|draw|click|press|fill|work out|calculate)\b|'
                      rf'\b(?:type|write|draw|click|press|fill|work out|calculate)\b.*?\b(?:in|using|with|inside)\s+'
                      rf'(?:the\s+)?(?:{APPS})\b', re.I)

# target keyword pattern -> (label, ordered (tool, tier, how) rows)
ROUTES = (
    (r'\b(?:excel|spreadsheets?|workbooks?|xlsx)\b|\.xlsx?\b', 'spreadsheet', (
        ('office_xlsx', 'api', 'read/write cells and formulas, read back'),
        ('office_automation', 'structured', "Excel's own object model in a hidden instance"),
        ('open', 'api', 'then open the saved workbook so the user sees it'),
        ('app_act', 'structured', 'only if the user asked to work in the Excel window'))),
    (r'\b(?:word documents?|docx|word)\b|\.docx?\b', 'document', (
        ('office_docx', 'api', 'paragraphs and tables, read back'),
        ('office_automation', 'structured', "Word's own object model"),
        ('open', 'api', 'then open the document to show it'))),
    (r'\bblender\b|\.blend\b|\b3d (?:model|object|scene)', 'blender', (
        ('blender_task', 'api', 'create objects and save a NEW .blend in background Blender, read back. Example: value '
                                'cylinder.blend, folder jarvis test folder, content {"operation":"create","objects":'
                                '[{"type":"cylinder","name":"JarvisCylinder","location":[0,0,0],"scale":[1,1,1]}]} '
                                '(a default cylinder is radius 1 m, depth 2 m; scale it for other sizes)'),
        ('open', 'api', 'then open the saved .blend in Blender so the user sees it'),
        ('screen_act', 'gui', 'only for what the templates cannot do, inside the open Blender window'))),
    (r'\b(?:vs ?code|visual studio code|code editor)\b|\bnew (?:coding )?project\b', 'code', (
        ('create_file', 'api', 'write project files with exact contents (or write_code for generated code)'),
        ('vscode_cli', 'api', 'open the folder/file in VS Code so the user sees it'),
        ('run_command', 'api', 'run or test it only when the user asked (approval required)'),
        ('app_act', 'structured', 'type in the editor only if the user asked to type there'))),
    (r'\b(?:obsidian|notes?|vault|memory|brain|knowledge)\b', 'notes', (
        ('knowledge_search', 'api', "search Jarvis's memory vault"),
        ('list_files', 'api', 'count and list vault notes and folders'),
        ('read_file', 'api', 'read notes'),
        ('create_file', 'api', 'write the new note into the vault folder'),
        ('open', 'api', 'then open it in Obsidian to show it'))),
    (r'\bnotepad\b|\.txt\b|\b(?:shopping|to-?do|grocery|task) list\b', 'text', (
        ('app_open', 'structured', 'open Notepad (a fresh tab) when the user asked for Notepad'),
        ('app_act', 'structured', 'type the text (app_open gives a new empty tab): value=type, content {"text": "..."}'),
        ('app_act', 'structured', 'then value=save_as, content {"text": "<full path of the file>"}: saves through the '
                                  'Save As dialog and checks the file exists'),
        ('create_file', 'api', 'write the file directly when the user did not ask for Notepad'),
        ('read_file', 'api', 'read the saved file back to verify'))),
    (r'\bcalculator\b|\bcalculat\w+|\bwork out\b|\bhow much is\b', 'calculation', (
        ('app_open', 'structured', 'use the Calculator app when the user asked for it'),
        ('app_act', 'structured', 'type the whole calculation with digits and + - * / ending in =, e.g. 1234*56-789= '
                                  '(never words); the changes show the display'),
        ('think', 'api', 'otherwise compute directly and show the working'))),
    (r'\bpaint\b|\bdraw\b|\bcanvas\b|\bsketch\b', 'drawing', (
        ('app_open', 'structured', 'open Paint and its tools by ref'),
        ('screen_act', 'gui', 'draw on the canvas, which has no controls; save via the menu by ref'))),
    (r'https?://|\b[a-z0-9-]+\.(?:com|org|net|io|dev|ai|in|edu|gov)\b|\bwebsite\b|\bweb ?page\b|\bonline\b|\bwikipedia\b', 'web', (
        ('web_open', 'structured', 'open and read the page in Jarvis\'s Chrome (refs); web_act to click or fill'),
        ('realtime_query', 'api', 'live data from a documented public API when one fits'),
        ('web_search', 'api', 'find which page to open when no URL is given'),
        ('deerflow_web_research', 'api', 'multi-source research questions'))),
    (r'\b(?:youtube|spotify)\b', 'media', (
        ('media_search', 'api', 'search the service'),
        ('mcp_call', 'api', 'YouTube/Spotify MCP connectors for lookups'),
        ('media_control', 'structured', 'control playback'))),
    (r'\b(?:gmail|e-?mails?|inbox)\b', 'email', (
        ('gmail_api_list', 'api', 'Gmail API (sends always ask first)'),)),
    (r'\b(?:files?|folders?)\b', 'files', (
        ('list_files', 'api', 'list'), ('read_file', 'api', 'read'), ('create_file', 'api', 'create'),
        ('modify_file', 'api', 'edit'), ('open', 'api', 'open in its app to show the user'))),
)
SCREEN_AWARE = ('After an API/code tool changes something the user can see (file, workbook, .blend, note), open it in its '
                'app so the user sees the result, and read it back to verify. Use the screen tools to observe and act '
                'only where no API does the job or the user asked for the app itself.')


def guide(goal, offered):
    """Planner hint rows for the targets in the goal, using only tools offered in this task."""
    text = str(goal or '')
    explicit = EXPLICIT.search(text)
    rows = []
    for pattern, label, order in ROUTES:
        if not re.search(pattern, text, re.I):
            continue
        usable = [{'tool': tool, 'tier': tier, 'how': how} for tool, tier, how in order if tool in offered]
        if usable:
            rows.append({'target': label, 'order': usable})
    if not rows:
        return []
    rule = ('The user explicitly asked to use the app itself: do the work in that app on screen (app_*/screen_act); '
            'API tools may only read or verify the result.' if explicit else
            'Prefer the first usable API/code/MCP tool; use screen control only where none fits.')
    return rows[:4] + [{'target': 'policy', 'rule': rule, 'screen_aware': SCREEN_AWARE}]
