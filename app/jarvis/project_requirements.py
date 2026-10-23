"""PIRAE language layer: classify project utterances, extract requirements, detect conflicts, score clarifications.

Deterministic and model-free. Phrases are recognised by their grammatical shape ("add X", "don't use X",
"make the Y more Z"), not by a list of example sentences. Concepts group common synonyms so that
"no cloud services" conflicts with "sync through a cloud API"; any other word is its own topic.
"""
import re

INTENTS = ('new_project', 'reference', 'location', 'add_requirement', 'modify_requirement', 'remove_requirement',
           'constraint', 'priority', 'progress', 'why', 'design', 'remaining', 'blockers', 'completed', 'missing',
           'better_way', 'pause', 'resume', 'overnight', 'switch', 'revert', 'permission', 'answer', 'none')
# Concept families. Only used to relate words; any unknown word is still a topic of its own.
CONCEPTS = {
    'network': {'cloud', 'online', 'internet', 'api', 'apis', 'web', 'remote', 'sync', 'server', 'servers', 'saas', 'network',
                'upload', 'http', 'telemetry', 'offline'},
    'interface': {'ui', 'interface', 'gui', 'design', 'look', 'theme', 'dark', 'light', 'futuristic', 'frontend', 'dashboard',
                  'layout', 'style', 'visual', 'screen', 'window', 'colour', 'color', 'animation'},
    'power': {'battery', 'power', 'energy', 'charging'},
    'performance': {'performance', 'fast', 'faster', 'speed', 'optimize', 'optimise', 'optimization', 'optimisation', 'latency',
                    'cpu', 'ram', 'memory', 'efficient'},
    'storage': {'database', 'db', 'sqlite', 'storage', 'persist', 'persistence', 'save', 'files'},
    'testing': {'test', 'tests', 'testing', 'verification', 'verify', 'qa'},
    'security': {'security', 'secure', 'password', 'credentials', 'encryption', 'privacy', 'private'},
    'documentation': {'docs', 'documentation', 'readme', 'manual', 'guide'},
}
STOP = {'the', 'a', 'an', 'it', 'this', 'that', 'to', 'and', 'or', 'of', 'for', 'with', 'my', 'our', 'your', 'me', 'please',
        'also', 'actually', 'jarvis', 'more', 'some', 'any', 'be', 'is', 'are', 'should', 'must', 'can', 'will', 'all', 'do',
        'make', 'use', 'using', 'add', 'include', 'look', 'feel', 'everything', 'thing', 'things', 'just', 'really', 'very',
        'project', 'app', 'application', 'program', 'feature', 'support', 'want', 'need', 'like', 'new', 'into', 'on', 'in'}
TYPES = [('unreal', r'\bunreal\b|\bue5?\b'), ('blender', r'\bblender\b|\b3d (?:scene|model|environment|asset)s?\b|\brender(?:ing)?\b'),
         ('document', r'\b(?:document|report|essay|letter|proposal|presentation|slides|resume|manual|ebook)\b'),
         ('research', r'\b(?:research|investigate|compare|survey|literature|study)\b'),
         ('data', r'\b(?:data analysis|analy[sz]e|dataset|csv|spreadsheet|statistics|chart)\b'),
         ('automation', r'\b(?:automat\w*|script|bot|workflow|schedule)\b'),
         ('software', r'\b(?:app|application|program|software|tool|website|web app|game|service|api|cli|desktop|dashboard|utility|plugin|extension)\b')]
NEW_PROJECT = re.compile(r'^(?:(?:please |can you |could you )?(?:create|start|begin|make|build|set up|setup|kick off|develop)\s+'
                         r'(?:me\s+)?(?:a |an )?(?:brand )?new\s+(\w[\w \-\'/]{0,240}?)|new project(?: called (.+))?)(?:[:,.]\s*(.*))?$', re.I | re.S)
# A restriction on project work: a constraint verb plus something a project is made of. Deleting is never a constraint.
NEGATED_CONSTRAINT = re.compile(r"^(?:do not|don'?t|never|stop)\s+(?:use|using|modify|modifying|change|changing|touch|touching|edit|"
                                r"editing|depend on|rely on|add|include|rewrite|rewriting)\b.*\b(?:file|files|module|modules|code|database|db|"
                                r"api|apis|cloud|reference|project|implementation|feature|library|libraries|framework|dependency|"
                                r"dependencies|class|function|ui|interface|design|service|services|internet|network|server)\b", re.I)
# Inside an active project any restriction on how work is done is a constraint ("but don't modify it").
NEGATED_IN_PROJECT = re.compile(r"^(?:do not|don'?t|never|stop)\s+(?:use|using|modify|modifying|change|changing|touch|touching|edit|"
                                r"editing|delete|deleting|depend on|rely on|call|add|include|rewrite|rewriting)\b", re.I)
PROJECT_NOUNS = {'project', 'app', 'application', 'program', 'software', 'tool', 'utility', 'website', 'site', 'game', 'service',
                 'api', 'cli', 'dashboard', 'plugin', 'extension', 'bot', 'script', 'automation', 'document', 'report', 'essay',
                 'presentation', 'deck', 'book', 'ebook', 'scene', 'model', 'environment', 'level', 'world', 'animation', 'analysis',
                 'dataset', 'research', 'study', 'workflow', 'pipeline', 'system', 'library', 'package', 'prototype', 'mod', 'blender', 'unreal'}


def project_request(text):
    """NEW_PROJECT match only when the subject's head is something a project produces, not a branch, file or tab."""
    match = NEW_PROJECT.match(clean(text))
    if not match:
        return None
    if match[1] is None:
        return match
    head = re.split(r'\s+(?:that|which|to|for|called|of|with|about|before|after|so)\s+', match[1].strip(), 1, flags=re.I)[0]
    return match if set(re.findall(r'[a-z]+', head.casefold())[:4]) & PROJECT_NOUNS else None


def words(text):
    return [w for w in re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", str(text or '').casefold()) if w not in STOP]


def topics(text):
    """Concept families plus remaining content words."""
    found = set()
    for word in words(text):
        concepts = {name for name, members in CONCEPTS.items() if word in members}
        found |= {'concept:' + c for c in concepts} or {word}
    return found


def project_type(text):
    for name, pattern in TYPES:
        if re.search(pattern, text or '', re.I):
            return name
    return None


def clean(text):
    return re.sub(r'^(?:jarvis[, ]+)', '', str(text or '').strip(), flags=re.I).strip().rstrip('.!?').strip()


def classify(text, *, has_project=False, pending=None):
    """(intent, details) for one utterance. 'none' means not a project utterance; let ordinary routing take it."""
    t = clean(text)
    match = project_request(t)
    if match:
        subject = (match[1] or 'project').strip()
        rest = (match[3] or match[2] or '').strip()
        return 'new_project', {'subject': subject, 'objective': rest}
    if not has_project:
        return 'none', {}
    # Conversational lead-ins carry no requirement meaning ("Actually, use no cloud services").
    body = re.sub(r'^(?:actually|ok(?:ay)?|so|and|but|oh|well|wait|hmm|right)[,]?\s+', '', t, flags=re.I)
    low = body.casefold()
    rules = [
        ('accept_recommendation', r'accept (?:recommendation|suggestion) (\d+)'),
        ('overnight', r'(?:finish|complete|do|continue)(?: (?:the|all|any))? (?:safe )?(?:remaining|rest|leftover)(?: (?:safe|of the))?(?: work| tasks)?(?: of it)? (?:overnight|tonight)|(?:work on|run) (?:the|this) project overnight'),
        ('progress', r'(?:explain|tell me|give me|report|what(?:\'s| is)) (?:your |the )?(?:current )?(?:progress|status)(?: (?:on|of) (?:the|this) project)?|how(?:\'s| is) (?:the|this|my) project (?:going|coming along)|what are you working on(?: (?:in|for) (?:the|this) project)?'),
        ('remaining', r"what(?:'s| is) left|what remains|what(?:'s| is) remaining|what(?:'s| is) still (?:to do|missing from the plan)"),
        ('completed', r'what (?:have|did) you (?:completed?|finish(?:ed)?|done)|what(?:\'s| is) (?:done|finished|completed)'),
        ('blockers', r'what are the blockers|what(?:\'s| is) blocking(?: you| it| the project)?|(?:are there|any) blockers'),
        ('why', r'why did you (?:choose|pick|use|go with|decide on) (?:that|the|this) (.+)|why (?:that|this) (architecture|approach|design)'),
        ('design', r'show (?:me )?(?:the )?(?:current )?(design|plan|requirements|architecture|spec(?:ification)?)|what are the (?:current )?requirements'),
        ('missing', r'check (?:whether|if) (?:something|anything)(?: important)? is missing|is (?:anything|something) missing|what am i missing'),
        ('better_way', r'can you think of a better (?:way|approach)|is there a better (?:way|approach)'),
        ('revert', r"i(?:'ve| have)? changed my mind|undo (?:that|the last) (?:change|requirement)|revert (?:that|the last) change"),
        ('pause', r'(?:pause|hold|stop working on) (?:the |this )?project'),
        ('resume', r'(?:continue|resume|carry on)(?: (?:the|this) project| where you (?:stopped|left off)| working)?'),
        ('switch', r'(?:switch to|go back to) (?:the )?(?:project )?(.+?)(?: project)?'),
        ('priority', r'(?:prioriti[sz]e|focus on) (.+?)(?: first)?|make (?:this|that|(.+?)) (?:the )?(?:highest|top) priority|do (.+?) first'),
        ('permission', r'(?:you (?:can|may)|go ahead and|feel free to) (?:modify|edit|change|update) (?:the )?(.+)'),
        ('reference', r'(?:use|treat) (?:my |the )?(.+?) as (?:a |the )?reference|reference (?:my |the )?(.+)|use (?:the )?existing (.+?) (?:code|implementation)(?: where possible)?'),
        ('location', r'(?:save|put|store|create|keep) (?:it|the project|everything) (?:in|into|at|under) (.+)|use (?:my )?(.+?) folder(?: for (?:it|the project))?|(?:the )?(?:location|destination|folder) (?:is|should be) (.+)'),
    ]
    for intent, pattern in rules:
        found = re.fullmatch(pattern, body, re.I)  # Original case: targets may be paths and names.
        if found:
            return intent, {'target': next((g for g in found.groups() if g), '') if found.groups() else ''}
    if NEGATED_IN_PROJECT.match(low) or re.match(r'^(?:use|with) no ', low) or re.match(r'^(?:everything|it) (?:must|should) (?:run|work|stay|be) ', low) \
            or re.match(r'^(?:it )?(?:must|must not|should not|cannot|can\'?t) ', low) or re.match(r'^(?:without|no more) ', low) \
            or re.search(r'\b(?:keep the old|don\'?t change|do not change)\b', low):
        return 'constraint', {}
    if re.match(r'^(?:remove|drop|delete|get rid of|take out|forget about|no longer (?:need|want)|skip)\b', low):
        return 'remove_requirement', {}
    if re.match(r'^(?:make|change|switch|replace|use .+ instead|keep|turn|redesign|rework|improve|simplify|rename)\b', low) \
            or re.search(r'\binstead\b', low):
        return 'modify_requirement', {}
    if re.match(r'^(?:add|include|also|it should|it needs to|support|implement|i (?:also )?want|i(?:\'d| would) like|let it|plus)\b', low):
        return 'add_requirement', {}
    if pending:
        return 'answer', {}
    return 'none', {}


def requirement_text(text):
    """Strip conversational lead-ins; keep the requirement itself."""
    t = clean(text)
    t = re.sub(r'^(?:also|actually|and|plus|oh|ok(?:ay)?|so|but)[, ]+', '', t, flags=re.I)
    t = re.sub(r'^(?:please |can you |could you |i want (?:you to )?|i(?:\'d| would) like (?:you to )?|let\'?s )', '', t, flags=re.I)
    return t[0].upper() + t[1:] if t else t


def polarity(text):
    low = clean(text).casefold()
    if re.match(r"^(?:do not|don'?t|never|stop|use no|with no|without|no more|must not|should not|cannot|can'?t)\b", low) \
            or re.search(r'\b(?:no|zero|without any) (?:\w+ ){0,2}(?:cloud|internet|network|online|api|apis|services?|dependencies|telemetry)\b', low) \
            or re.search(r'\b(?:offline|locally only|local only)\b', low):
        return 'prohibit'
    return 'require'


def prohibited_topics(text):
    """For a prohibition, the topics that must not appear: 'run offline' prohibits the network concept."""
    found = topics(text)
    if re.search(r'\boffline\b|\blocal(?:ly)? only\b', text or '', re.I):
        found.add('concept:network')
    return found - {'concept:testing'} if 'test' not in (text or '').casefold() else found


def conflicts(requirement, existing):
    """Active requirements with the same topic and opposite polarity."""
    mine = prohibited_topics(requirement['text']) if requirement['polarity'] == 'prohibit' else topics(requirement['text'])
    rows = []
    for other in existing:
        if other['id'] == requirement['id'] or other['status'] != 'active' or other['polarity'] == requirement['polarity']:
            continue
        theirs = prohibited_topics(other['text']) if other['polarity'] == 'prohibit' else topics(other['text'])
        shared = mine & theirs
        if shared:
            rows.append({'requirement': other['id'], 'text': other['text'], 'shared': sorted(shared)})
    return rows


def related(text, requirements, minimum=1):
    """Existing requirements a modification or removal most plausibly refers to."""
    mine = topics(text)
    scored = []
    for row in requirements:
        if row['status'] != 'active':
            continue
        shared = mine & topics(row['text'])
        if len(shared) >= minimum:
            scored.append((len(shared) / max(1, len(topics(row['text']))), row))
    return [row for _, row in sorted(scored, key=lambda pair: -pair[0])]


# --- clarification policy ---------------------------------------------------------------------------------------------
# Slot -> (impact, rework, risk) for an unanswered slot. Tunable engineering heuristics, not calibrated probabilities.
SLOTS = {
    'objective': (1., 1., .6), 'location': (.5, .4, .9), 'references': (.4, .4, .2), 'technology': (.7, .9, .3),
    'platform': (.5, .7, .2), 'interface_style': (.3, .3, .1), 'deliverables': (.5, .4, .1),
}
QUESTIONS = {
    'objective': 'What should the {subject} do?',
    'location': 'Where should I save it?',
    'references': "Is there an existing project I should use as reference? I'll treat it as read-only.",
    'technology': 'Do you have a preferred language or framework, or should I choose one?',
    'platform': 'Which platform should it run on?',
    'interface_style': 'Any preference for how the interface should look?',
    'deliverables': 'What should the finished result include?',
}
WEIGHTS = {'impact': .4, 'rework': .3, 'risk': .3}


def clarification_priority(uncertainty, impact, rework, risk, weights=None):
    """U(r) * [0.4 I + 0.3 W + 0.3 R]."""
    w = weights or WEIGHTS
    return round(uncertainty * (w['impact'] * impact + w['rework'] * rework + w['risk'] * risk), 4)


def plan_questions(slots, *, ask_threshold=.4, default_threshold=.2, weights=None):
    """Decide per slot: ask now, provisional default (routine choice), or silent safe default.

    `slots` maps slot -> uncertainty (0 known ... 1 unknown). Authorization is decided elsewhere.
    """
    decisions = []
    for slot, uncertainty in slots.items():
        impact, rework, risk = SLOTS[slot]
        score = clarification_priority(uncertainty, impact, rework, risk, weights)
        action = 'ask' if score >= ask_threshold else 'provisional' if score >= default_threshold else 'default'
        decisions.append({'slot': slot, 'uncertainty': uncertainty, 'score': score, 'action': action})
    return sorted(decisions, key=lambda d: -d['score'])
