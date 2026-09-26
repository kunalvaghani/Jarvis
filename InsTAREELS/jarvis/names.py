"""Common spoken names; rank real candidates without inventing targets."""
from difflib import SequenceMatcher
import re

ALIASES = {"vs code": "visual studio code", "vscode": "visual studio code",
    "visual code": "visual studio code", "google chrome": "chrome", "browser": "chrome",
    "ms word": "word", "microsoft word": "word", "ms excel": "excel",
    "windows explorer": "file explorer", "explorer": "file explorer", "calc": "calculator",
    "note pad": "notepad", "you tube": "youtube", "download": "downloads",
    "my downloads": "downloads", "my documents": "documents", "my desktop": "desktop"}


def normalize(value):
    numbers = "zero one two three four five six seven eight nine ten".split()
    value = re.sub(r"\b(person|profile) (zero|one|two|three|four|five|six|seven|eight|nine|ten)\b",
        lambda m: m[1] + " " + str(numbers.index(m[2].lower())), value, flags=re.I)
    value = re.sub(r"([a-z])([0-9])|([0-9])([a-z])", lambda m: " ".join(x for x in m.groups() if x), value.casefold())
    value = re.sub(r"\bdot\b", ".", value)
    return " ".join(re.sub(r"[^\w]+", " ", value.replace("_", " ")).split())


def common(value):
    value = normalize(value)
    return ALIASES.get(value, value)


def rank(query, labels):
    """Return all strong matches, keeping ambiguous candidates for the user."""
    query = common(query)
    exact = [label for label in labels if common(label) == query]
    if exact:
        return exact
    compact = [label for label in labels if common(label).replace(" ", "") == query.replace(" ", "")]
    if compact:
        return compact
    words = set(query.split()) - {"my", "the"}
    if not words:
        return []
    partial = [label for label in labels if words <= set(common(label).split())]
    if partial:
        return partial
    if len(query) < 5:
        return []
    scored = [(SequenceMatcher(None, query, common(label)).ratio(), label) for label in labels]
    scored = sorted((score, label) for score, label in scored if score >= .86)
    if not scored:
        return []
    best = scored[-1][0]
    return [label for score, label in reversed(scored) if score >= best - .08]


def spelling_score(query, label):
    """Score spelling and close spoken forms without inventing a target name."""
    query, label = common(query).replace(" ", ""), common(label).replace(" ", "")
    if not query or not label or max(len(query), len(label)) > 120:
        return 0.0
    # Edit distance includes swapped adjacent letters: chrmoe -> chrome.
    rows = [list(range(len(label) + 1))]
    for i, letter in enumerate(query, 1):
        row = [i]
        for j, other in enumerate(label, 1):
            cost = min(row[j - 1] + 1, rows[-1][j] + 1, rows[-1][j - 1] + (letter != other))
            if i > 1 and j > 1 and letter == label[j - 2] and query[i - 2] == other:
                cost = min(cost, rows[-2][j - 2] + 1)
            row.append(cost)
        rows.append(row)
    score = 1 - rows[-1][-1] / max(len(query), len(label))
    # Limited sound/spacing repair, still requiring close spelling evidence.
    def sounds(text):
        text = text.replace("ph", "f").replace("ck", "k").replace("c", "k").replace("z", "s")
        text = re.sub(r"([a-z])\1+", r"\1", text)
        return text[:1] + re.sub(r"[aeiou]", "", text[1:])
    if len(query) >= 4 and sounds(query) == sounds(label) and score >= .65:
        score = max(score, .83)
    return score


def rank_spelling(query, labels):
    """Match only supplied app/control names; retain near ties as choices."""
    labels = list(labels)
    matched = rank(query, labels)
    if matched:
        return matched
    key = common(query).replace(" ", "")
    if len(key) < 3:
        return []
    scored = [(spelling_score(query, label), label) for label in labels]
    threshold = .75 if len(key) <= 4 else .72
    scored = sorted(((score, label) for score, label in scored if score >= threshold), reverse=True)
    if not scored:
        return []
    return [label for score, label in scored if score >= scored[0][0] - .09]
