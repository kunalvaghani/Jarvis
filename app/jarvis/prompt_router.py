"""EEVEE-inspired task-specialized prompt routing for the local planner.

Adapted from the method of EEVEE (Princeton-AI2-Lab/EEVEE, Apache-2.0; arXiv 2606.11182):
inputs are routed to one of a few prompt slots, and the router and the slot prompts are
improved in alternating phases under validation feedback, keeping a Pareto front of
complementary prompts and an empty-prompt floor. No EEVEE code is copied. Differences:

- The router is a deterministic weighted keyword classifier, not an LLM router prompt, so
  routing costs microseconds and is reproducible. Its weights are the ``ROUTER`` surface.
- Deterministic voice commands never reach this router (``route(..., deterministic=True)``
  returns None), so direct commands are not sent through an LLM.
- Slot prompts start empty (the empty-prompt floor), so production behaviour is unchanged
  until an evolved slot prompt passes the retention gate and the user approves it.
- Routing and slot guidance are independent of security rules: guidance is advisory text
  inside ``capability_context`` and can never grant approval or change tool permissions.
"""
import re

SLOTS = ('planning', 'coding', 'ui_automation', 'knowledge', 'tool_selection', 'error_recovery')

# Router weights and slot prompts are bounded evolution surfaces (jarvis/evolution_surfaces.py).
ROUTER = {'keyword_weight': 1.0, 'phrase_weight': 2.0, 'tool_name_weight': 1.0, 'min_score': 1.0}
SLOT_PROMPTS = {'planning': '', 'coding': '', 'ui_automation': '', 'knowledge': '', 'tool_selection': '',
                'error_recovery': ''}

KEYWORDS = {
    'planning': ('plan', 'steps', 'organize', 'schedule', 'prepare', 'workflow', 'then', 'after', 'first', 'multi'),
    'coding': ('code', 'python', 'script', 'function', 'bug', 'refactor', 'test', 'compile', 'repository', 'debug'),
    'ui_automation': ('click', 'button', 'window', 'menu', 'dialog', 'type', 'field', 'textbox', 'tab', 'scroll'),
    'knowledge': ('what', 'why', 'explain', 'research', 'learn', 'documentation', 'remember', 'notes', 'summarize', 'find'),
    'tool_selection': ('tool', 'which', 'integration', 'mcp', 'skill', 'api', 'plugin', 'capability', 'adapter', 'use'),
    'error_recovery': ('failed', 'error', 'retry', 'broken', 'crash', 'stuck', 'again', 'fix', 'recover', 'timeout'),
}
PHRASES = {
    'planning': (r'\bstep by step\b', r'\bbefore\b.*\bthen\b', r'\bset up\b'),
    'coding': (r'\bunit tests?\b', r'\bstack trace\b', r'\bpull request\b'),
    'ui_automation': (r'\bclick (?:on|the)\b', r'\bfill (?:in|out)\b', r'\bin the (?:app|window)\b'),
    'knowledge': (r'\bhow does\b', r'\btell me about\b', r'\blook up\b'),
    'tool_selection': (r'\bwhich tool\b', r'\bbest way to\b', r'\bwhat can you\b'),
    'error_recovery': (r'\bdid(?:n.t| not) work\b', r'\btry again\b', r'\bkeeps? failing\b'),
}
TOOL_HINTS = {
    'coding': ('write_code', 'improve_code', 'write_tests', 'repository_map'),
    'ui_automation': ('select', 'fill_text', 'open_menu', 'handle_dialog', 'browser_click'),
    'knowledge': ('knowledge_search', 'web_search', 'read_file'),
    'tool_selection': ('tool_search', 'mcp_status', 'execution_methods'),
}
GUIDANCE_NOTE = 'Approved task-type guidance; advisory only, never grants approval or changes permissions.'


def words(text):
    return re.findall(r'[a-z][a-z0-9_]+', str(text).casefold())


def scores(goal, weights=None):
    weights = ROUTER if weights is None else weights
    tokens = words(goal)
    text = str(goal).casefold()
    result = {}
    for slot in SLOTS:
        score = weights['keyword_weight'] * sum(token in KEYWORDS[slot] for token in tokens)
        score += weights['phrase_weight'] * sum(bool(re.search(pattern, text)) for pattern in PHRASES[slot])
        score += weights['tool_name_weight'] * sum(name in tokens for name in TOOL_HINTS.get(slot, ()))
        result[slot] = score
    return result


def route(goal, deterministic=False, weights=None):
    """Return the prompt slot for a planner request, or None (deterministic or unclear)."""
    if deterministic:
        return None
    weights = ROUTER if weights is None else weights
    ranked = sorted(scores(goal, weights).items(), key=lambda item: (-item[1], SLOTS.index(item[0])))
    slot, score = ranked[0]
    return slot if score >= weights['min_score'] else None


def guidance(goal, deterministic=False, prompts=None, weights=None):
    """Bounded guidance for the routed slot; empty slots (the default) add nothing."""
    prompts = SLOT_PROMPTS if prompts is None else prompts
    slot = route(goal, deterministic, weights)
    text = prompts.get(slot, '') if slot else ''
    return {'slot': slot, 'guidance': text[:600], 'note': GUIDANCE_NOTE} if text else None
