"""Text file saved (e.g. Notepad): the file exists, was written during the task, and holds the expected text."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence

from .base import Verdict, Verifier, judged

POINT = re.compile(r'^\s*(?:[-*•]|\d+[.)])\s+(.+?)\s*$')


def titled_list_problems(lines: List[str], title_words: Sequence[str], items: Sequence[str],
                         title_pattern: Optional[str] = None) -> List[str]:
    """The user's list rule (2026-10-30): a title naming the topic, then exactly the items as points."""
    problems = []
    first = lines[0] if lines else ''
    named = all(re.search(rf'\b{re.escape(w)}\b', first, re.I) for w in title_words) and (
        title_pattern is None or re.search(title_pattern, first, re.I) is not None)
    if not lines or POINT.match(first) or not named:
        problems.append(f'first line is not a title naming the list: {lines[:1]!r}')
    matches = [POINT.match(line) for line in lines[1:]]
    found = sorted(m.group(1).strip().lower().rstrip('.') for m in matches if m)
    if not all(matches) or found != sorted(i.lower() for i in items):
        problems.append(f'items are not exactly {len(items)} points {"/".join(items)}: {lines[1:]!r}')
    return problems


class TextFileSaved(Verifier):
    NAME = 'text_file_saved'
    READS = frozenset({'file'})

    def check(self, *, path: str | Path, started_after: Optional[float] = None, lines: Optional[Sequence[str]] = None,
              title_words: Sequence[str] = (), title_pattern: Optional[str] = None,
              items: Optional[Sequence[str]] = None, **_: Any) -> Verdict:
        target = Path(path)
        evidence: Dict[str, Any] = {'path': str(target)}
        if not target.is_file():
            return judged([f'{target} was not saved'], evidence)
        stat = target.stat()
        evidence.update(bytes=stat.st_size, modified=stat.st_mtime)
        problems: List[str] = []
        if started_after is not None and stat.st_mtime < started_after:
            problems.append(f'{target.name} was not written during this task')
        text = target.read_text(encoding='utf-8-sig', errors='replace')
        found = [line for line in text.splitlines() if line.strip()]
        evidence['lines'] = found[:20]
        if lines is not None and [line.strip() for line in found] != [line.strip() for line in lines]:
            problems.append(f'content is {found[:10]!r}, expected {list(lines)!r}')
        if items is not None:
            problems += titled_list_problems(found, title_words, items, title_pattern)
        return judged(problems, evidence)


def check(**params: Any) -> Verdict:
    return TextFileSaved().check(**params)
