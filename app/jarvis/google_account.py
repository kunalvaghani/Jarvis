"""The Google account Jarvis uses in the browser (config google.account; the user's main account).

Chrome Person 1 holds several Google accounts. Jarvis's code writes Gmail links in the generic form
https://mail.google.com/mail/u/0/...; before a page opens they are pointed at the configured account:
- Gmail: /mail/u/0/ becomes /mail/u/<slot>/, the slot Gmail itself chooses for ?authuser=<account> (looked up
  once per Jarvis run, then remembered: it changes only when accounts are added to Chrome);
- Drive, Docs, Sheets, Slides: authuser=<account> is added to the link.
No account configured: links are unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

FILES_HOSTS = frozenset({'drive.google.com', 'docs.google.com', 'sheets.google.com', 'slides.google.com'})
_SLOTS: Dict[str, str] = {}


def configured_account(base: Any = None) -> str:
    try:
        path = Path(base or Path(__file__).resolve().parent.parent) / 'config' / 'config.json'
        section = json.loads(path.read_text(encoding='utf-8')).get('google') or {}
    except (OSError, ValueError, TypeError):
        return ''
    return str(section.get('account', '') if isinstance(section, dict) else '').strip()


def slot_from(url: str) -> Optional[str]:
    found = re.search(r'mail\.google\.com/mail/u/(\d+)/', url or '')
    return found.group(1) if found else None


def for_account(url: str, account: str, lookup: Callable[[str], Optional[str]]) -> str:
    """The link pointed at ``account``. ``lookup(account)`` returns Gmail's slot for it (None: unknown)."""
    if not account:
        return url
    parts = urlsplit(url if '//' in url else 'https://' + url)
    host = (parts.hostname or '').lower()
    if host == 'mail.google.com' and re.match(r'^/mail/u/0(?:/|$)', parts.path):
        slot = _SLOTS.get(account.casefold())
        if slot is None:
            slot = lookup(account)
            if slot is None:
                return url  # unknown: leave the link as it is (the page shows which account opened)
            _SLOTS[account.casefold()] = slot
        return urlunsplit(parts._replace(path=re.sub(r'^/mail/u/0', f'/mail/u/{slot}', parts.path, count=1)))
    if host in FILES_HOSTS and 'authuser=' not in parts.query:
        query = (parts.query + '&' if parts.query else '') + 'authuser=' + account
        return urlunsplit(parts._replace(query=query))
    return url
