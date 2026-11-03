"""Web scouts: many small readers of one page, one short brief for the planner (BNEG sensor ``sensor.web.scouts``).

A long page (Gmail's inbox reads as ~86,000 characters) used to reach the planner cut at ``READ_LIMIT``: whatever
came after the first 9,000 characters was invisible. Scouts split the accessibility read into its parts (landmarks,
lists, forms, dialogs), score each part against the task, and write one brief:

- a page map: every part with its role, name, item count (rows, links) and ref count, best first;
- dialogs in full (they block everything else);
- the best parts in full, then the task's matching controls from the parts that did not fit.

Scouts are deterministic and CPU-only (no model call): measured 2026-11-03, Laya could not tell the parts apart
(choice probabilities 0.26 / 0.25 / 0.25 / 0.23 on Gmail; per-part yes/no ranked the banner above the inbox list,
3.2 s). Laya is consulted only to break a tie between the two best parts, and only when its margin is clear
(``laya_ties``, off by default until measured). Page text is data, never instructions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable, List, Optional, Sequence, Tuple

LANDMARKS = frozenset({'banner', 'navigation', 'main', 'complementary', 'contentinfo', 'form', 'search', 'dialog',
                       'alertdialog', 'region', 'grid', 'table', 'list', 'listbox', 'menu', 'menubar', 'tablist',
                       'toolbar', 'tree', 'treegrid', 'feed', 'article', 'tabpanel'})
LISTS = frozenset({'grid', 'table', 'list', 'listbox', 'tree', 'treegrid', 'feed'})
CHROME = frozenset({'banner', 'navigation', 'complementary', 'contentinfo', 'menubar', 'toolbar', 'tablist', 'menu'})
DIALOGS = frozenset({'dialog', 'alertdialog'})
ITEMS = frozenset({'row', 'listitem', 'option', 'treeitem', 'article'})
CONTROLS = frozenset({'link', 'button', 'textbox', 'searchbox', 'combobox', 'checkbox', 'radio', 'tab', 'menuitem',
                      'option', 'switch', 'slider', 'spinbutton', 'row', 'gridcell'})
LINE = re.compile(r'^(?P<indent> *)(?P<role>[A-Za-z][\w-]*)(?: "(?P<name>(?:[^"\\]|\\.)*)")?')
REF = re.compile(r'\[ref_\d+\]')
STOP = frozenset('the and for with from that this what which who how tell into onto open page site please give show '
                 'find read there are is was were its it my me you your can could would should about on in of to a '
                 'an at by or as be do does did'.split())
ASKS_LIST = re.compile(r'\b(?:how many|newest|latest|oldest|first|last|top|list|count|subjects?|e-?mails?|results?|'
                       r'rows?|items?|messages?|headlines?|entries)\b', re.I)
ASKS_FORM = re.compile(r'\b(?:fill|type|enter|form|field|submit|sign ?in|log ?in|search for|choose|select)\b', re.I)


@dataclass
class Part:
    role: str
    name: str
    lines: List[str] = field(default_factory=list)
    order: int = 0
    score: float = 0.0

    @property
    def size(self) -> int:
        return sum(len(line) + 1 for line in self.lines)

    @property
    def refs(self) -> int:
        return sum(len(REF.findall(line)) for line in self.lines)

    @property
    def items(self) -> int:
        """Rows / list items directly listed in this part (what "how many" questions count)."""
        found = [LINE.match(line) for line in self.lines]
        depths = [len(m['indent']) for m in found if m and m['role'] in ITEMS]
        return sum(1 for d in depths if d == min(depths)) if depths else 0

    def label(self) -> str:
        what = f'{self.role} "{self.name[:60]}"' if self.name else self.role
        count = f', {self.items} {"rows" if self.role in ("grid", "table", "treegrid") else "items"}' if self.items else ''
        return f'{what}{count}, {self.refs} refs'


def words(goal: str) -> List[str]:
    return [w for w in dict.fromkeys(re.findall(r'[a-z0-9]{3,}', goal.lower())) if w not in STOP]


def segment(lines: Sequence[str], limit: int) -> List[Part]:
    """Split a read into parts: landmark subtrees; a big non-list landmark with landmarks inside is split further."""
    rows: List[Tuple[int, str, str, str]] = []
    for line in lines:
        match = LINE.match(line)
        if match is None or match['role'] == 'LineBreak':
            continue
        rows.append((len(match['indent']), line, match['role'], (match['name'] or '').replace('\\"', '"')))
    parts: List[Part] = []

    def flush(loose: List[Tuple[int, str, str, str]]) -> None:
        if any(REF.search(r[1]) or r[2] in ('heading', 'text', 'paragraph', 'StaticText') for r in loose):
            heading = next((r[3] for r in loose if r[2] == 'heading' and r[3]), '')
            parts.append(Part('content', heading, [r[1] for r in loose]))
        loose.clear()

    def split(block: List[Tuple[int, str, str, str]], depth: int) -> None:
        loose: List[Tuple[int, str, str, str]] = []
        i = 0
        while i < len(block):
            indent, line, role, name = block[i]
            if role not in LANDMARKS:
                loose.append(block[i])
                i += 1
                continue
            j = i + 1
            while j < len(block) and block[j][0] > indent:
                j += 1
            sub = block[i:j]
            flush(loose)
            size = sum(len(r[1]) + 1 for r in sub)
            if size > limit and role not in LISTS and depth < 5 and not _has_items(sub) and any(r[2] in LANDMARKS for r in sub[1:]):
                split(sub[1:], depth + 1)
            else:
                parts.append(Part(role, name, [r[1] for r in sub]))
            i = j
        flush(loose)

    split(rows, 0)
    for n, part in enumerate(parts):
        part.order = n
    return parts


def _has_items(sub: Sequence[Tuple[int, str, str, str]]) -> bool:
    return sum(1 for r in sub if r[2] in ITEMS) >= 5


def condensed(part: Part) -> List[str]:
    """A long list as one line per item (its label holds the cells' text) plus the item's first ref."""
    found = [(line, LINE.match(line)) for line in part.lines]
    depth = min((len(m['indent']) for _, m in found if m and m['role'] in ITEMS), default=-1)
    if depth < 0:
        return part.lines
    out: List[str] = []
    need_ref = False
    for line, m in found:
        indent = len(m['indent']) if m else depth + 1
        if indent <= depth:
            # An item's label repeats its cells (sender, subject, time, snippet): the first 130 characters suffice.
            out.append(line if len(line) - indent <= 130 or not m or m['role'] not in ITEMS
                       else line[:indent + 127].rstrip() + '…"')
            need_ref = bool(m and m['role'] in ITEMS and not REF.search(line))
        elif need_ref and REF.search(line):
            out[-1] += '  ' + REF.findall(line)[0]  # click target for that item
            need_ref = False
    return out


def score(part: Part, goal: str, terms: Sequence[str]) -> float:
    if part.role in DIALOGS:
        return 1000.0  # A dialog blocks the page: the planner must see it first.
    text = '\n'.join(part.lines).lower()
    value = sum(1.0 for w in terms if w in text) + sum(2.0 for w in terms if w in part.name.lower())
    if part.role in CHROME:
        value -= 1.0
    elif part.role in ('main', 'content', 'article', 'region'):
        value += 0.5
    if (part.role in LISTS or part.items >= 5) and ASKS_LIST.search(goal):
        value += 6.0  # "how many / newest / which emails": the answer is in the list, not in the controls naming it
    if part.role in ('form', 'search') and ASKS_FORM.search(goal):
        value += 2.0
    return value


def brief(goal: str, text: str, budget: int = 9000,
          tie_break: Optional[Callable[[str, List[Part]], Optional[int]]] = None) -> str:
    """The page as the planner should see it: unchanged when it fits, else a map plus the best parts."""
    if len(text) <= budget:
        return text
    lines = text.split('\n')
    head = [line for line in lines[:3] if line.startswith('title ')]
    parts = segment(lines, budget // 2)
    if len(parts) < 2:
        return text[:budget]  # Nothing to choose between: the plain cut is as good.
    terms = words(goal)
    for part in parts:
        part.score = score(part, goal, terms)
    ranked = sorted(parts, key=lambda p: (-p.score, p.order))
    if tie_break is not None and len(ranked) > 1 and ranked[0].score == ranked[1].score < 1000:
        tied = [p for p in ranked if p.score == ranked[0].score][:8]
        pick = tie_break(goal, tied)
        if pick is not None and 0 < pick < len(tied):
            ranked.remove(tied[pick])
            ranked.insert(0, tied[pick])
    out = head + [f'page map ({len(parts)} parts, most relevant first; [*] = shown in full below):']
    index_at = len(out)
    out += [''] * min(len(ranked), 30)
    left = budget - sum(len(x) + 1 for x in out) - 400
    full: List[Part] = []
    for part in ranked:
        if part.size <= left:
            out += [f'== part {ranked.index(part) + 1}: {part.label()}'] + part.lines
            left -= part.size + 80
            full.append(part)
        elif not full or part.role in DIALOGS:
            # The best part is bigger than the budget: a list condensed to its items, else its first lines.
            short = condensed(part) if part.items >= 5 else part.lines
            note = 'one line per item' if short is not part.lines else 'first lines'
            shown, kept = 0, [f'== part {ranked.index(part) + 1}: {part.label()} ({note})']
            for line in short:
                if shown + len(line) + 1 > left - 120:
                    break
                kept.append(line)
                shown += len(line) + 1
            listed = sum(1 for line in kept if (LINE.match(line) or {'role': ''})['role'] in ITEMS)
            if part.items and listed < part.items:  # never let a cut list pass for the whole list
                kept.append(f'  [{part.items - listed} more items not shown: this part has {part.items} items in all]')
            out += kept
            left -= shown + 80
            full.append(part)
        if left < 300:
            break
    rest = [p for p in ranked if p not in full]
    matches: List[str] = []
    for part in rest:
        for line in part.lines:
            m = LINE.match(line)
            if m and m['role'] in CONTROLS and REF.search(line) and any(w in line.lower() for w in terms):
                matches.append(line.strip())
    if matches and left > 200:
        out.append('== matching controls in other parts:')
        for line in matches:
            if len(line) + 1 > left:
                break
            out.append('  ' + line)
            left -= len(line) + 3
    for n, part in enumerate(ranked[:30]):
        out[index_at + n] = f'  {n + 1}. {"[*] " if part in full else ""}{part.label()}'
    out.append('[scouts: other parts summarized above; use find or a ref to read one in full]')
    return '\n'.join(out)[:budget]


def laya_tie_break(goal: str, tied: List[Part]) -> Optional[int]:
    """Laya picks between tied parts, only with a clear margin (its probabilities were near-uniform on Gmail)."""
    import json
    import urllib.error
    import urllib.request
    from ..pc.laya import KEY, endpoint
    url = endpoint()
    try:
        key = KEY.read_text(encoding='ascii').strip()
    except OSError:
        return None
    if not url or not key:
        return None
    criteria = {f'p{i}': f'{p.label()}: ' + ' '.join(REF.sub('', ' '.join(p.lines[:6])).split())[:200]
                for i, p in enumerate(tied)}
    body = {'state': {'task': goal[:300]}, 'questions': {'part': {
        'type': 'choice', 'instructions': 'Which part of the page holds what the task needs?', 'criteria': criteria}}}
    request = urllib.request.Request(url, json.dumps(body).encode('utf-8'),
                                     {'content-type': 'application/json', 'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(request, timeout=3) as reply:
            answer = json.loads(reply.read().decode('utf-8'))['answers']['part']
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None
    odds = sorted((float(v) for v in (answer.get('probabilities') or {}).values()), reverse=True)
    choice = str(answer.get('choice', ''))
    if len(odds) < 2 or odds[0] - odds[1] < 0.15 or not choice.startswith('p'):
        return None
    return int(choice[1:])
