"""Semantic disambiguation using current accessibility evidence only."""
import re
from .ui_controls import label_key, UNSAFE_INFERRED


def disambiguate(choices, query):
    if len(choices) <= 1 or UNSAFE_INFERRED.search(query):
        return choices
    urls = {c.get("href") for c in choices}
    if len(urls) == 1 and None not in urls and "" not in urls and all(c["role"] == "Hyperlink" for c in choices):
        return choices[:1]
    tokens = set(label_key(query).split())
    scoped = [c for c in choices if tokens <= set(label_key(c["name"] + " " + c.get("context", "")).split())]
    return scoped if len(scoped) == 1 else choices


def scoped_matches(controls, query):
    from .ui_controls import matches
    choices = matches(controls, query)
    if not choices and not UNSAFE_INFERRED.search(query):
        parts = re.fullmatch(r"(.+?) (?:for|in|under|of) (.+)", query, re.I)
        if parts:
            choices = matches(controls, parts[1])
            context = set(label_key(parts[2]).split())
            choices = [c for c in choices if context <= set(label_key(c.get("context", "")).split())]
    return disambiguate(choices, query)
