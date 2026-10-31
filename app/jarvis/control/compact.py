"""Compact page and window reads (flag control.compact_reads, default off).

A read lists one node per line: `<indent>role "name" [state] [ref]`. Two kinds of line carry nothing the
planner can use, and they are most of a read's size:

- a nameless container (`generic ""`, `rowgroup ""`, UIA `Group ""`) with no state: it is dropped and its
  children move up one level;
- `text "X"` or `image "X"` directly under a node already named X (`heading "Data Tables"` > `text "Data Tables"`,
  `link "Home"` > `image "Home"`): the parent carries the same words and is the thing to act on.

Every other line is kept unchanged except for its indent, so all text, cells, links, controls and their refs
survive. Lines that are not nodes (notices, truncation marks) are kept as they are.
"""
from __future__ import annotations

import re
from typing import List, Tuple

LINE = re.compile(r'^(?P<indent> *)(?P<role>\w[\w ]*?) "(?P<name>[^"]*)"(?P<rest>.*)$')
CONTAINERS = frozenset({'generic', 'none', 'presentation', 'paragraph', 'rowgroup', 'Section', 'section', 'div',
                        'group', 'Group', 'Custom', 'Pane', 'LayoutTable', 'LayoutTableRow', 'LayoutTableCell'})
REPEATS = frozenset({'text', 'StaticText', 'image', 'img', 'Image'})
STATE = re.compile(r"\b(?:focused|checked|selected|expanded|required|invalid)\b|\bvalue=")


def compact(read: str) -> str:
    out: List[str] = []
    # (original indent, indent for this node's children, name its children may repeat; a dropped node passes on its parent's)
    stack: List[Tuple[int, int, str]] = []
    for line in read.split('\n'):
        match = LINE.match(line)
        if match is None:
            out.append(line)
            continue
        indent = len(match['indent']) // 2
        while stack and stack[-1][0] >= indent:
            stack.pop()
        level = stack[-1][1] if stack else 0
        role, name, rest = match['role'], match['name'], match['rest']
        if role in CONTAINERS and not name and not STATE.search(rest):
            stack.append((indent, level, stack[-1][2] if stack else ''))  # Dropped: children take its place.
            continue
        if role in REPEATS and stack and name and name == stack[-1][2]:
            continue  # Repeats its parent's name.
        out.append('  ' * level + line[len(match['indent']):])
        stack.append((indent, level + 1, name))
    return '\n'.join(out)
