"""Fixed routes for clear, common requests (flag control.api_routes, default off).

A local planner model is the weakest link on requests whose steps are always the same. In the varied live gates
(2026-10-31 and 2026-11-01) it asked "what task should I complete?" for a fully stated Blender request, put
arguments in the wrong fields, declared a website question answered without reading the page, and repeated
a Calculator operation. The usual remedy for small tool-calling models is to route unambiguous requests in code
and keep the model for what is ambiguous (deterministic intent routing); this module does that for three kinds:

- **Blender primitive**: "add a <shape> ... name it N ... save as F.blend in <folder>" -> one `blender_task` step
  (the existing adapter: approval, background Blender, independent readback, then the file opens in Blender).
- **Calculator arithmetic**: the words become an expression; it is typed once into Calculator, and the display
  must show the value Jarvis computes exactly (fractions), or the result is reported as unconfirmed.
- **Website question**: open the named page, read it in full, and answer only from the page text; numbers in the
  answer must appear on the page, otherwise the route steps aside and the planner continues.

Anything a parser is not sure of returns None before any action, and the normal planner runs unchanged.
"""
from __future__ import annotations

from fractions import Fraction
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

Cancelled = Callable[[], bool]

# ---- Blender -------------------------------------------------------------------------------------------------
SHAPES = ('cube', 'sphere', 'cylinder', 'cone', 'torus', 'plane')
NUMBER = r'(\d+(?:\.\d+)?)'
UNIT = r'\s*(?:m\b|metres?\b|meters?\b)?'
BLEND = re.compile(r'\b([\w.()-]+\.blend)\b', re.I)
NAMED = re.compile(r'\b(?:name|call)\s+it\s+["\']?([A-Za-z0-9_][A-Za-z0-9_.-]{0,62})', re.I)
FOLDER = re.compile(r'\.blend\s+(?:in|into|to)\s+(?:my\s+|the\s+)?([\w -]{1,60}?folder)\b', re.I)
RADIUS = re.compile(r'\bradius\s+(?:of\s+)?' + NUMBER + UNIT, re.I)
DEPTH = re.compile(r'\b(?:depth|height)\s+(?:of\s+)?' + NUMBER + UNIT + r'|' + NUMBER + UNIT + r'\s+(?:deep|tall|high)\b', re.I)
SIDE = re.compile(NUMBER + UNIT + r'\s+on\s+each\s+side|\bside(?:\s+length)?\s+(?:of\s+)?' + NUMBER + UNIT + r'|'
                  r'\bsize\s+(?:of\s+)?' + NUMBER + UNIT, re.I)
OTHER_UNITS = re.compile(r'\d\s*(?:cm|mm|km|inch|inches|in\b|feet|foot|ft\b)', re.I)
CENTRE = re.compile(r'\bat\s+the\s+(?:centre|center|origin)\b|\bat\s+\(?0\s*,\s*0\s*,\s*0\)?', re.I)
LOCATION = re.compile(r'\bat\s+\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)?', re.I)


def value(match: 're.Match[str]') -> float:
    return float(next(g for g in match.groups() if g))


def blender_step(goal: str) -> Optional[Dict[str, Any]]:
    """The one blender_task step a fully stated primitive request needs, or None when anything is unclear."""
    if not re.search(r'\bblender\b', goal, re.I) or not re.search(r'\b(?:add|create|make|insert)\b', goal, re.I):
        return None
    shapes = {s for s in SHAPES if re.search(r'\b' + s + r's?\b', goal, re.I)}
    files, named, folder = BLEND.findall(goal), NAMED.search(goal), FOLDER.search(goal)
    if len(shapes) != 1 or len(set(files)) != 1 or not named or not folder or OTHER_UNITS.search(goal):
        return None
    shape = shapes.pop()
    item: Dict[str, Any] = {'type': shape, 'name': named.group(1).rstrip('.,')}
    at = LOCATION.search(goal)
    item['location'] = [float(v) for v in at.groups()] if at and not CENTRE.search(goal) else [0, 0, 0]
    radius, depth, side = RADIUS.search(goal), DEPTH.search(goal), SIDE.search(goal)
    if shape in ('cylinder', 'cone'):
        if side:
            return None
        scale: Dict[str, float] = {}
        if radius:
            scale['radius'] = value(radius)
        if depth:
            scale['depth'] = value(depth)
        if scale:
            item['scale'] = scale  # The adapter turns {radius, depth} into Blender's scale (default r 1, depth 2).
    elif shape == 'sphere':
        if side or depth:
            return None
        if radius:
            item['scale'] = {'radius': value(radius)}
    elif shape == 'cube':
        if radius or depth:
            return None
        if side:
            half = value(side) / 2  # Blender's default cube is 2 m on each side.
            item['scale'] = [half, half, half]
    elif radius or depth or side:
        return None  # Torus and plane sizes are not parsed here; the planner handles them.
    return {'action': 'blender_task', 'value': files[0], 'folder': folder.group(1).strip(),
            'content': json.dumps({'operation': 'create', 'objects': [item]})}


# ---- Calculator ----------------------------------------------------------------------------------------------
WORD_OPS = (('multiplied by', '*'), ('times', '*'), ('divided by', '/'), ('over', '/'), ('plus', '+'), ('minus', '-'),
            ('x', '*'), ('×', '*'), ('÷', '/'), ('*', '*'), ('/', '/'), ('+', '+'), ('-', '-'))
STEP = re.compile(r'^(?:then\s+)?(multiply|divide|add|subtract)\s+(?:the\s+result|it|that)\s+(?:by|to|from)\s+' + NUMBER + r'$',
                  re.I)


def _chain(text: str) -> Optional[List[Tuple[str, Fraction]]]:
    """'1234 times 56 minus 789' -> [('', 1234), ('*', 56), ('-', 789)] (applied left to right)."""
    text = ' '.join(text.replace(',', ' ').split())
    first = re.match(NUMBER + r'\s*', text)
    if not first:
        return None
    chain = [('', Fraction(first.group(1)))]
    rest = text[first.end():]
    while rest:
        for word, op in WORD_OPS:
            if rest.lower().startswith(word) and (not word.isalpha() or not rest[len(word):len(word) + 1].isalpha()):
                number = re.match(r'\s*' + NUMBER + r'\s*', rest[len(word):])
                if not number:
                    return None
                chain.append((op, Fraction(number.group(1))))
                rest = rest[len(word) + number.end():]
                break
        else:
            return None
    return chain


def calculation(goal: str) -> Optional[Tuple[str, Fraction]]:
    """(keys to type, exact value) for an arithmetic request that names Calculator, or None."""
    if not re.search(r'\bcalculator\b', goal, re.I):
        return None
    body = re.split(r'\b(?:work out|calculate|compute|what is|what\'s)\b|:', goal, maxsplit=1, flags=re.I)
    if len(body) != 2:
        return None
    text = re.split(r'\s*(?:,\s*)?\band\s+tell\s+me\b|\s*[?.!]\s*$|\s*,\s*and\s+(?:show|give)\b', body[1], maxsplit=1,
                    flags=re.I)[0].strip(' ,.')
    parts = [p.strip(' ,') for p in re.split(r',?\s*\bthen\b\s*', text, flags=re.I) if p.strip(' ,')]
    adding = re.fullmatch(r'add\s+' + NUMBER + r'\s+(?:and|to)\s+' + NUMBER, parts[0], re.I) if parts else None
    taking = re.fullmatch(r'subtract\s+' + NUMBER + r'\s+from\s+' + NUMBER, parts[0], re.I) if parts else None
    if adding:
        chain = [('', Fraction(adding.group(1))), ('+', Fraction(adding.group(2)))]
    elif taking:
        chain = [('', Fraction(taking.group(2))), ('-', Fraction(taking.group(1)))]
    else:
        found = _chain(parts[0]) if parts else None
        if found is None:
            return None
        chain = found
    for part in parts[1:]:
        step = STEP.match(part)
        if not step:
            return None
        op = {'multiply': '*', 'divide': '/', 'add': '+', 'subtract': '-'}[step.group(1).lower()]
        chain.append((op, Fraction(step.group(2))))
    value = chain[0][1]
    keys = _number(chain[0][1])
    for op, number in chain[1:]:
        if op == '/' and number == 0:
            return None
        value = {'+': value + number, '-': value - number, '*': value * number, '/': value / number}[op]
        keys += op + _number(number) + '='  # '=' after each operation: left to right in any Calculator mode.
    return keys, value


def _number(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else format(float(value), 'g')


def _shown(display: str) -> Optional[Fraction]:
    try:
        return Fraction(re.sub(r'[,\s  ]', '', display))
    except (ValueError, ZeroDivisionError):
        return None


# ---- Website question ----------------------------------------------------------------------------------------
SITE = re.compile(r'(?:https?://\S+|\bwww\.[\w.-]+(?:/\S*)?|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|gov|edu|dev|'
                  r'app|co|uk|info|me|ai)(?:/[^\s,?]*)?)', re.I)
ANSWER_LIMIT = 9000


WIKIPEDIA = re.compile(r"^\s*(?:on|from|according to)\s+wikipedia,?\s+(?P<q>.+?)\s*\??\s*$", re.I)
WIKI_ARTICLE = re.compile(r'\bwikipedia\s+(?:page|article)\s+(?:(?:called|titled|named|for|on)\s+)?["“](?P<title>[^"”]{2,120})["”]',
                          re.I)


GMAIL_READ = re.compile(r'\b(?:gmail|my inbox|my e-?mails?)\b', re.I)
GMAIL_WRITE = re.compile(r'\b(?:draft|send|sent it|compose|write|reply|forward|delete|archive|mark|label|move|'
                         r'star|unsubscribe|attach)\b', re.I)
GMAIL_FROM = re.compile(r'\bsearch(?:es)?\s+(?:for\s+)?(?:e-?mails?|messages?)\s+from\s+(?P<who>[\w.@+-]+)', re.I)


def gmail_question(goal: str) -> Optional[Tuple[str, str]]:
    """(page, question) for read-only Gmail questions ("tell me the subject of the newest email in my inbox",
    "search for emails from Google and tell me how many..."). Anything that writes goes to the planner."""
    if not GMAIL_READ.search(goal) or GMAIL_WRITE.search(goal) or \
            not re.search(r'\b(?:tell me|what|which|who|how many|list|show me)\b', goal, re.I):
        return None
    found = GMAIL_FROM.search(goal)
    if found:
        from urllib.parse import quote
        return f'https://mail.google.com/mail/u/0/#search/{quote("from:" + found.group("who").strip())}', goal
    return 'https://mail.google.com/mail/u/0/#inbox', goal


def site_question(goal: str) -> Optional[Tuple[str, str]]:
    """(page, question) for "On <site>, <question>?" with exactly one site; None otherwise."""
    gmail = gmail_question(goal)
    if gmail:
        return gmail
    if not goal.rstrip().endswith('?') and not re.match(r'\s*(?:what|who|which|how)\b', goal, re.I) \
            and not re.search(r'\btell me\b', goal, re.I):
        return None
    sites = SITE.findall(goal)
    wiki = WIKIPEDIA.match(goal)
    article = WIKI_ARTICLE.search(goal)
    if not sites and article:
        # 'On the Wikipedia page "List of largest cities", ...': the named article itself.
        from urllib.parse import quote
        sites = ['en.wikipedia.org/wiki/' + quote(article.group('title').strip().replace(' ', '_'))]
    elif not sites and wiki:
        # "On Wikipedia, what year was the Eiffel Tower completed?": Wikipedia's own search goes to the article.
        from urllib.parse import quote_plus
        subject = re.sub(r'^(?:what|which|when|who|how|where|why)\b.*?\b(?:was|were|is|are|did|does|do)\s+(?:the\s+)?',
                         '', wiki.group('q'), flags=re.I)
        subject = re.sub(r'\s+(?:completed|built|born|founded|opened|made|released|located|invented)\b.*$', '', subject,
                         flags=re.I).strip(' ?.')
        if not subject or subject.lower() in ('who', 'what', 'which', 'when', 'where', 'why', 'how'):
            subject = re.sub(r'^(?:who|what|which|when|where|why|how)\s+', '', wiki.group('q'), flags=re.I)
        sites = [f'en.wikipedia.org/w/index.php?search={quote_plus(subject)}']
    if len(sites) != 1 or re.search(r'\b(?:log ?in|sign ?in|buy|order|submit|send|post|fill|book (?:a|an|me)|booking)\b', goal, re.I):
        return None
    page = str(sites[0]).rstrip('.,/')
    return (page, goal) if page else None


def _focus(text: str, question: str) -> str:
    """The page text, or the lines around the question's own words when the page is long."""
    if len(text) <= ANSWER_LIMIT:
        return text
    words = {w.casefold() for w in re.findall(r'"([^"]+)"|\b([A-Z][\w-]+(?:\s+[A-Z][\w-]+)*)', question) for w in w if w}
    words |= {w.casefold() for w in re.findall(r'\b\w{5,}\b', question)}
    lines = text.split('\n')
    keep: set[int] = set()
    for index, line in enumerate(lines):
        if any(w in line.casefold() for w in words):
            keep.update(range(max(0, index - 6), min(len(lines), index + 7)))
    picked = '\n'.join(lines[i] for i in sorted(keep))
    return (picked or text)[:ANSWER_LIMIT]


def grounded(answer: str, page: str) -> bool:
    """Every number the answer states appears on the page (counts up to 20 may be counted, not shown)."""
    flat = re.sub(r'[,\s  ]', '', page)
    for number in re.findall(r'\d+(?:[.,]\d+)*', answer):
        plain = number.replace(',', '')
        if plain not in flat and not (plain.isdigit() and int(plain) <= 20):
            return False
    return True


# ---- Running -------------------------------------------------------------------------------------------------
def run(actions: Any, goal: str, cancelled: Cancelled) -> Optional[str]:
    """Brain._run's hook: a finished answer for a request one of the fixed routes covers, else None."""
    from . import flags
    from .control.backends import pc_backend
    config = getattr(actions, 'config', None)
    if pc_backend(config if isinstance(config, dict) else {}) == 'agent_desktop':
        from .control.pc.fast_paths import run as pc_fast_path
        answer = pc_fast_path(goal, lambda kind, detail: _approved(actions, kind, detail, cancelled))
        if answer is not None:
            return answer  # "minimize Spotify", "copy X to the clipboard": one command, then a fresh read.
        side = SIDE_BY_SIDE.match(goal)
        if side:
            arranged = _side_by_side(actions, [side.group('a').strip(), side.group('b').strip()], cancelled)
            if arranged:
                return arranged
        start = START_MENU.match(goal)
        if start:  # same outcome as clicking it in Start: the app's verified launch (live C14, 2026-11-03)
            opened = json.loads(actions.control().app_open(start.group('app').strip(), '', cancelled).splitlines()[0])
            if opened.get('ok'):
                return f'Opened {start.group("app").strip()} (checked: its window appeared).'
    if not flags.enabled(config, 'control', 'api_routes'):
        return None
    from .blender_live import live_request, run as live_blender
    live = live_request(goal)
    if live is not None:
        return live_blender(actions, live, cancelled)  # Watched in a visible Blender (user request 2026-11-01).
    step = blender_step(goal)
    if step is not None:
        return _blender(actions, step, cancelled)
    calc = calculation(goal)
    if calc is not None:
        return _calculator(actions, calc, cancelled)
    draft = gmail_draft(goal)
    if draft is not None:
        return _gmail_draft(actions, draft, cancelled)
    asked = site_question(goal)
    if asked is not None:
        return _website(actions, asked[0], asked[1], cancelled)
    return None


# ---- Gmail draft (never sent) ------------------------------------------------------------------------------------
GMAIL_DRAFT = re.compile(r'\b(?:create|write|make|compose|prepare|save)\b[^.]*?\bdraft\b[^.]*?\bto\s+'
                         r'(?P<to>[\w.+-]+@[\w-]+(?:\.[\w-]+)+)[^"“]*?\bsubject\s+["“](?P<subject>[^"”]{1,150})["”]'
                         r'(?:[^"“]*?\bbody\s+["“](?P<body>[^"”]{0,2000})["”])?', re.I)


def gmail_draft(goal: str) -> Optional[Dict[str, str]]:
    """{to, subject, body} for "create a draft to <address> with subject "..." and body "..."". A request that
    asks to send is not a draft: it goes to the planner and its approvals."""
    if not re.search(r'\bgmail\b', goal, re.I):
        return None
    if re.search(r'\bsend\b', goal, re.I) and not re.search(r"\b(?:do not|don't|never|without)\s+send", goal, re.I):
        return None
    found = GMAIL_DRAFT.search(goal)
    if not found:
        return None
    return {'to': found.group('to'), 'subject': found.group('subject').strip(), 'body': found.group('body') or ''}


def _gmail_draft(actions: Any, draft: Dict[str, str], cancelled: Cancelled) -> Optional[str]:
    """Gmail's compose link with the fields filled, saved by Gmail's autosave, then checked in Drafts. Send is
    never clicked. The draft is created once: no retry after an uncertain step."""
    from urllib.parse import quote
    control = actions.control()
    actions.report('brain', f'Fixed route: Gmail draft "{draft["subject"]}" (not sent)')
    if not _approved(actions, 'gmail draft', f'Create a Gmail draft to {draft["to"]} with subject '
                                             f'"{draft["subject"]}" (it is not sent)', cancelled):
        return 'Did not create the Gmail draft: it was not approved. Nothing was written.'
    # A compose link alone is not saved (live 2026-11-03: Drafts stayed empty); Gmail saves once the message is
    # edited. So: recipient and subject from the link, the body typed into "Message Body", then Gmail's "Saved".
    url = ('https://mail.google.com/mail/u/0/?view=cm&fs=1&to=' + quote(draft['to']) + '&su=' + quote(draft['subject']))
    actions.report('tool', 'control: web_open Gmail compose (not sent)')
    opened = control.web_open(url, cancelled)
    head = json.loads(opened.split('\n', 1)[0]) if opened.startswith('{') else {}
    if head.get('ok') is False:
        return 'Gmail compose did not open, so no draft was made. ' + str(head.get('result', ''))[:200]
    body_ref = ''
    for _ in range(8):  # the compose form renders after the page loads
        body = re.search(r'textbox "Message Body"[^\n]*\[(ref_\d+)\]', control.web_read(cancelled, 'interactive'))
        if body:
            body_ref = body.group(1)
            break
        time.sleep(1.0)
    if not body_ref:
        return 'Gmail compose opened, but its message box was not found, so no draft was made. Nothing was sent.'
    actions.report('tool', 'control: web_act fill Message Body (draft only)')
    control.web_act('fill', {'ref': body_ref, 'value': draft['body'] or ' '}, cancelled)
    for _ in range(12):  # Gmail shows "Saved" next to the buttons once the draft is stored
        time.sleep(1.0)
        control.web_read(cancelled, 'all')
        if re.search(r'"(?:Draft saved|Saved)\b', str(getattr(control, 'last_web', '') or '')):
            break
    actions.report('tool', 'control: web_open Gmail drafts (check)')
    control.web_open('https://mail.google.com/mail/u/0/#drafts', cancelled)
    for _ in range(8):  # the Drafts list fills in after the page loads
        text = str(getattr(control, 'last_web', '') or '')
        if any(draft['subject'] in row for row in re.findall(r'^\s*row "([^"]*)"', text, re.M)):
            return (f'Finished: saved a Gmail draft to {draft["to"]} with subject "{draft["subject"]}". It was not '
                    'sent (checked: it is listed in Drafts).')
        if cancelled():
            break
        time.sleep(1.0)
        control.web_read(cancelled, 'all')
    return (f'The draft "{draft["subject"]}" is not listed in Gmail Drafts after saving, so I cannot confirm it was '
            'made. It was not sent; I did not try again, to avoid duplicates. Please check Drafts.')


START_MENU = re.compile(r"^\s*(?:please\s+)?(?:open\s+the\s+start\s+menu\s+and\s+)?(?:launch|open|start)\s+"
                        r"(?P<app>[\w .+-]{2,40}?)\s+from\s+(?:it|the\s+start\s+menu)\s*[.!]?\s*$", re.I)


SIDE_BY_SIDE = re.compile(r"^\s*(?:please\s+)?(?:open|put|place|show)\s+(?P<a>[\w .+-]{2,30}?)\s+and\s+"
                          r"(?P<b>[\w .+-]{2,30}?)\s+side\s+by\s+side\s*[.!]?\s*$", re.I)


def _side_by_side(actions: Any, apps: List[str], cancelled: Cancelled) -> Optional[str]:
    """Open two apps and give each half of the primary display; read the window list back (live C42)."""
    from .control.pc.runner import Runner
    service = actions.control()
    handles = []
    for app in apps:
        opened = json.loads(service.app_open(app, '', cancelled).splitlines()[0])
        if not opened.get('ok') or not opened.get('window'):
            return None
        handles.append(int(opened['window']))
    run = Runner()
    displays = run(['list-displays'], timeout_s=15)
    screen = next((d['bounds'] for d in (displays.data or []) if d.get('is_primary')), None) if displays.ok else None
    if not screen:
        return None
    # Window bounds use the same units as display bounds (checked live): no DPI scaling here. 48 = taskbar.
    width, height = int(screen['width']), int(screen['height']) - 48
    half = width // 2
    for index, handle in enumerate(handles):
        wid = f'w-{handle}'
        run(['restore', '--window-id', wid], timeout_s=15)
        run(['resize-window', '--window-id', wid, '--width', str(half), '--height', str(height)], timeout_s=15)
        run(['move-window', '--window-id', wid, f'--x={index * half}', '--y=0'], timeout_s=15)
    listed = run(['list-windows'], timeout_s=15)
    rows = {str(w.get('id')): w for w in (listed.data or []) if isinstance(w, dict)} if listed.ok else {}
    placed = [rows.get(f'w-{h}', {}).get('bounds') or {} for h in handles]
    if len(placed) != 2 or not all(placed) or float(placed[0].get('x', 0)) >= float(placed[1].get('x', 0)):
        return None
    return f'Opened {apps[0]} and {apps[1]} side by side (checked: left and right halves).'


def _approved(actions: Any, kind: str, detail: str, cancelled: Cancelled) -> bool:
    ask = getattr(actions, '_approve', None)
    if ask is None:
        return False
    try:
        ask(kind, detail, cancelled)
        return True
    except Exception:
        return False


def _blender(actions: Any, step: Dict[str, Any], cancelled: Cancelled) -> str:
    from .tools import ToolRegistry
    actions.report('brain', 'Fixed route: Blender ' + json.loads(step['content'])['objects'][0]['type'])
    return str(ToolRegistry(actions).execute(step, cancelled).evidence)


def _calculator(actions: Any, calc: Tuple[str, Fraction], cancelled: Cancelled) -> str:
    keys, expected = calc
    actions.report('brain', 'Fixed route: Calculator ' + keys)
    control = actions.control()
    actions.report('tool', 'control: app_open Calculator')
    control.app_open('Calculator', '', cancelled)
    actions.report('tool', 'control: app_act type ' + keys)
    control.app_act('type', {'text': keys}, cancelled)  # Typed once; never repeated after it was sent.
    actions.report('tool', 'control: app_read Calculator')
    read = control.app_read('Calculator', 'all', cancelled)
    found = re.search(r'Display is ([^"\]\n]+)', read)
    display = found.group(1).strip() if found else ''
    if _shown(display) != expected and _shown(display) != Fraction(format(float(expected), '.12g')):
        return (f'Typed {keys} into Calculator, but the display shows {display or "nothing readable"}, not the '
                f'expected {_number(expected)}. The keys were not typed again; please check Calculator.')
    return f'Finished: Calculator shows {display} ({keys.rstrip("=")}).'


REJECT_COOKIES = re.compile(r'button "(?P<label>(?:reject|decline|refuse)(?: all| additional| non-essential| optional)?'
                            r'(?: cookies)?|(?:use |allow )?(?:only )?(?:strictly )?necessary(?: cookies)?(?: only)?)"'
                            r'[^\n]*?\[(?P<ref>ref_\d+)\]', re.I)


def _website(actions: Any, page: str, question: str, cancelled: Cancelled) -> Optional[str]:
    control = actions.control()
    actions.report('brain', 'Fixed route: read ' + page + ' and answer from it')
    actions.report('tool', 'control: web_open ' + page)
    opened = control.web_open(page, cancelled)
    head = json.loads(opened.split('\n', 1)[0]) if opened.startswith('{') else {}
    text = str(getattr(control, 'last_web', '') or '')
    if head.get('ok') is False or len(text) < 50:
        actions.report('brain', f'Fixed route gave up: the page did not open or read ({len(text)} characters)')
        return None  # The page did not open or read; the planner can try another way.
    if re.search(r'\bcookies?\b', question, re.I) and re.search(r'\b(?:reject|decline|refuse|necessary|essential)\b',
                                                               question, re.I):
        # "reject non-essential cookies if a banner appears": the privacy-protective button, clicked once, then
        # a fresh read. No banner (the choice is already saved in the user's Chrome): nothing to do.
        found = REJECT_COOKIES.search(text)
        done = 'No cookie banner was showing, so nothing needed rejecting.'
        if found:
            done = f'The cookie banner was dismissed with its "{found.group("label")}" button.'
            actions.report('tool', f'control: web_act click {found.group("label")}')
            control.web_act('click', {'ref': found.group('ref')}, cancelled)
            time.sleep(1.0)
            control.web_read(cancelled, 'all')
            text = str(getattr(control, 'last_web', '') or text)
        question = (f'{question}\n(Already done by Jarvis: {done} '
                    'Answer only the rest, and say this in one short sentence.)')
    from . import flags
    if flags.enabled(getattr(actions, 'config', None), 'control', 'web_scouts'):
        from .control.web.scouts import brief
        page_text = brief(question, text, ANSWER_LIMIT)  # page map + best parts (sensor.web.scouts)
    else:
        page_text = _focus(text, question)
    if 'mail.google.com' in page:
        # Gmail's list rows carry sender, subject, time and snippet in one label: give the model just those.
        rows = re.findall(r'^\s*row "([^"]{8,})"', text, re.M)
        # Gmail fills the list in stages after the page loads (searches especially; 0, then 5, then 50 rows seen):
        # re-read until two reads agree, at most 6 more reads.
        for _ in range(6):
            if cancelled():
                break
            time.sleep(1.0)
            control.web_read(cancelled, 'all')
            text = str(getattr(control, 'last_web', '') or '')  # the full read, not the planner's cut view
            again = re.findall(r'^\s*row "([^"]{8,})"', text, re.M)
            settled = bool(rows) and len(again) == len(rows)
            rows = again
            if settled:
                break
        if not rows:
            return None  # Not the mail list (signed out, still loading): the planner decides.
        page_text = f'{len(rows)} email rows on this page, newest first:\n' + '\n'.join(
            f'{n}. {row[:300]}' for n, row in enumerate(rows, 1))
    reply = actions.brain.client.request('tool_text', cancelled, tool='think', context='', goal=(
        'Answer the question using ONLY this page text. Quote names and numbers exactly as the page shows them. '
        'Count carefully when asked how many. If the page text does not contain the answer, reply exactly: '
        f'NOT ON PAGE.\nQuestion: {question}\nPage text:\n{page_text}'))
    answer = ' '.join(str(reply.get('text', '') if isinstance(reply, dict) else reply).split())[:800]
    if not answer or 'NOT ON PAGE' in answer.upper() or not grounded(answer, text):
        why = 'no answer' if not answer else ('not on the page' if 'NOT ON PAGE' in answer.upper()
                                              else 'a number in the answer is not on the page')
        actions.report('brain', f'Fixed route gave up: {why} ({len(page_text)} of {len(text)} characters read)')
        return None  # Not answerable from this page: the planner continues (it can navigate further).
    return 'Finished: ' + answer
