"""The user's list rule (2026-10-30): any list Jarvis writes is a title naming its topic, then one point per item.

The compose prompt already asks for this, but text the planner types itself (app_act type) bypassed it, so a
shopping list arrived as bare lines (live S3, rounds 19-23). `titled()` applies the rule to such text when the
task asks for a list. Text that is not bare short item lines, or a goal that is not about a list, is unchanged.
"""
from __future__ import annotations

import re
from typing import List, Optional

TOPIC = re.compile(r"\b(?P<topic>to-?\s?do|[a-z]+)\s+list\b|\b(?P<check>checklist)\b", re.I)
LIST_OF = re.compile(r"\blist of (?P<of>[a-z]+(?: [a-z]+)?)", re.I)
POINT = re.compile(r'^\s*(?:[-*•]|\d+[.)])\s+\S')
SKIP_TOPICS = {'a', 'the', 'my', 'this', 'that', 'your', 'new', 'simple', 'short', 'long', 'to', 'in', 'on', 'of'}
MAX_ITEM = 80


def topic_title(goal: str) -> Optional[str]:
    """'Shopping List', 'To-Do List', 'Checklist' or 'Packing List' from the goal; None if it asks for no list."""
    of = LIST_OF.search(goal)
    if of:
        return of['of'].title() + ' List'
    for match in TOPIC.finditer(goal):
        if match['check']:
            return 'Checklist'
        topic = match['topic'].lower().replace(' ', '')
        if topic in ('todo', 'to-do'):
            return 'To-Do List'
        if topic not in SKIP_TOPICS:
            return topic.title() + ' List'
    return None


def titled(text: str, goal: str) -> str:
    title = topic_title(goal)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if title is None or len(lines) < 2 or any(len(line) > MAX_ITEM for line in lines):
        return text
    head: List[str] = []
    if re.search(r'\blist\b|checklist', lines[0], re.I) and not POINT.match(lines[0]):
        head, lines = [lines[0]], lines[1:]  # Already titled; only the items need points.
    if len(lines) < 1 or any(POINT.match(line) for line in lines):
        return text  # Already pointed (or mixed): the planner chose a layout; leave it.
    return '\n'.join((head or [title]) + ['- ' + line for line in lines])
