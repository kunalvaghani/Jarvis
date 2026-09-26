"""Open public websites/search URLs with an installed browser, without shell code."""
from urllib.parse import quote, quote_plus, urlsplit
import re
from .names import common, rank

SITES = {"youtube": "https://www.youtube.com/", "google": "https://www.google.com/",
    "spotify": "https://open.spotify.com/",
    "gmail": "https://mail.google.com/", "whatsapp": "https://web.whatsapp.com/",
    "github": "https://github.com/", "chatgpt": "https://chatgpt.com/"}


def url_for(name, search=False):
    if search:
        return "https://www.google.com/search?q=" + quote_plus(name)
    if common(name) in SITES:
        return SITES[common(name)]
    candidate = name if name.startswith(("https://", "http://")) else "https://" + name
    parts = urlsplit(candidate)
    if (parts.scheme not in {"https", "http"} or not parts.hostname or "." not in parts.hostname
            or parts.username or parts.password or re.search(r"[\s<>]", candidate)):
        raise ValueError("Name a website such as YouTube, a domain such as example.com, or say search followed by your query.")
    return candidate


def browser_args(apps, name):
    aliases = rank(name, apps)
    executables = []
    for alias in aliases:
        entry = apps[alias]
        args = entry if isinstance(entry, list) else [entry.get("executable", "")]
        if args and args[0] and args not in executables:
            executables.append(args)
    if len(executables) != 1:
        raise ValueError(f"Cannot uniquely identify the installed browser '{name}'. Say Chrome, Edge, or Firefox.")
    return executables[0]


def music_search_url(query, platform):
    query = query.strip()
    if not query or len(query) > 300:
        raise ValueError("Name a song, artist, playlist, or genre to play.")
    if platform == "youtube":
        return "https://www.youtube.com/results?search_query=" + quote_plus(query)
    if platform == "spotify":
        return "https://open.spotify.com/search/" + quote(query, safe="")
    raise ValueError("Choose Spotify or YouTube for music.")
