"""Deterministic, fail-closed public question policy. No model or network calls."""
import json
import os
from pathlib import Path
import re

DEFAULTS = dict(enabled=False, model='qwen/qwen3.8-27b', free_only=True,
    account_plan='unknown', free_tier_confirmed=False, dedicated_quota_confirmed=False,
    max_daily_requests=1000, max_daily_tokens=200000, max_minute_requests=30,
    max_minute_tokens=8000, timeout_seconds=90, allow_sensitive_data=False,
    live_tests_enabled=False, safety_margin=.1, max_output_tokens=1536,
    metadata_ttl_seconds=300, routing='auto')


def settings(value=None, environ=None):
    if value is not None and (not isinstance(value, dict) or set(value)-set(DEFAULTS)):
        raise ValueError('Unknown Groq configuration field.')
    result = {**DEFAULTS, **(value or {})}
    env = os.environ if environ is None else environ
    for name, default in DEFAULTS.items():
        raw = env.get('GROQ_' + name.upper())
        if raw is not None:
            try:
                if type(default) is bool:
                    if raw.lower() not in {'true','false'}: raise ValueError()
                    result[name] = raw.lower() == 'true'
                elif type(default) is int: result[name] = int(raw)
                elif type(default) is float: result[name] = float(raw)
                else: result[name] = raw
            except (ValueError, TypeError):
                raise ValueError('Invalid Groq setting: ' + name) from None
    for name in ('enabled','free_only','free_tier_confirmed','dedicated_quota_confirmed','allow_sensitive_data','live_tests_enabled'):
        if type(result[name]) is not bool: raise ValueError('Groq ' + name + ' must be boolean.')
    for name, maximum in [('max_daily_requests',1000),('max_daily_tokens',200000),('max_minute_requests',30),('max_minute_tokens',8000),('max_output_tokens',4096),('metadata_ttl_seconds',3600),('timeout_seconds',120)]:
        if type(result[name]) is not int or not 1 <= result[name] <= maximum:
            raise ValueError('Invalid conservative Groq limit: ' + name)
    if type(result['safety_margin']) not in {int,float} or not .05 <= result['safety_margin'] <= .5:
        raise ValueError('Groq safety margin must be 5–50 percent.')
    if result['account_plan'] not in {'unknown','free','paid'} or result['routing'] not in {'auto','local','public'}:
        raise ValueError('Invalid Groq account/routing policy.')
    if result['model'] != DEFAULTS['model']:
        raise ValueError('This adapter supports only the reviewed Groq Qwen model; deprecated models fall back locally.')
    # This integration deliberately has no paid dispatcher or blanket private upload.
    if not result['free_only'] or result['allow_sensitive_data']:
        raise ValueError('Paid or blanket sensitive-data dispatch is not implemented.')
    return result


def credential(base):
    value = os.environ.get('GROQ_API_KEY')
    if not value:
        path = Path(base) / 'secrets/groq.json'
        if not path.is_file(): return None
        if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (path,path.parent)) or path.stat().st_size > 8192:
            raise ValueError('Unsupported local Groq credential file.')
        try: value = json.loads(path.read_text(encoding='utf-8')).get('GROQ_API_KEY')
        except (ValueError, AttributeError): raise ValueError('Invalid local Groq credential file.') from None
    if not isinstance(value, str) or not 10 <= len(value) <= 300 or any(c.isspace() for c in value):
        raise ValueError('Invalid Groq credential format.')
    return value


SECRET = re.compile(r'(?i)(?:gsk_[a-z0-9]{10,}|sk-(?:proj-)?[a-z0-9_-]{12,}|-----BEGIN .*PRIVATE KEY|(?:passwords?|passwd|api[_ -]?keys?|secrets?|authorization|bearer|cookies?|(?:session[_-]?)?tokens?)\s*[:=]\s*\S+|\b\d{3}-\d{2}-\d{4}\b|[\w.+-]+@[\w.-]+\.[a-z]{2,})')
PRIVATE = re.compile(r'(?i)(?:[a-z]:[\\/]|\\\\|/(?:home|users|etc|mnt)/|\.env\b|\b(?:my|our|personal|private|confidential|credentials?|bank|accounts?|passwords?|ssh|memory|memories|remember|previous|continue|screenshots?|desktop|clipboard|downloads|documents|passport|ssn|patient|diagnosis|financial|identity)\b|(?:मेरे|मेरा|मेरी|पासवर्ड|खाता|निजी))')
ACTION = re.compile(r'(?i)\b(?:open|launch|delete|send|publish|upload|install|execute|run|click|type|save|turn down|volume|shutdown|restart|search my|fix my)\b|(?:खोलो|भेजो|चलाओ|हटाओ)')
PUBLIC = re.compile(r'(?i)^(?:please\s+)?(?:explain|compare|describe|derive|prove|design|outline|discuss|analyze|analyse|what (?:is|are)|how (?:does|do)|why (?:does|do)|give (?:a|an)|show (?:a|an)|explica|compara|describe|समझाओ|समझाइए|बताओ|तुलना|explain karo)\b')
FOLLOWUP = re.compile(r'(?i)\b(?:this|that|it|above|earlier|same|again|we|you said)\b')
COMPLEX = re.compile(r'(?i)\b(?:tradeoffs?|architecture|distributed|proof|prove|derive|algorithm|complexity|concurrency|quantum|cryptography|optimization|compare|debug|consistency|design|reasoning)\b')
CONTEXT = ('history','screen','conversation_context','pc_context','memory_context','catalog_context','live_app_context','realtime_context')


def classify(request):
    question = request.get('question','')
    if not isinstance(question,str) or not 3 <= len(question) <= 4000:
        return {'privacy':'UNKNOWN','complexity':'unknown','reason':'invalid_or_ambiguous'}
    if SECRET.search(question): return {'privacy':'SENSITIVE','complexity':'unknown','reason':'secret_pattern'}
    if request.get('task_kind','ask') != 'ask': return {'privacy':'INTERNAL','complexity':'unknown','reason':'local_executor_task'}
    if PRIVATE.search(question) or ACTION.search(question) or any(request.get(k) for k in CONTEXT):
        return {'privacy':'INTERNAL','complexity':'unknown','reason':'private_context_or_action'}
    if not PUBLIC.search(question.strip()) or FOLLOWUP.search(question):
        return {'privacy':'UNKNOWN','complexity':'unknown','reason':'uncertain_provenance'}
    difficulty = 'complex' if COMPLEX.search(question) or len(question)>300 else 'medium'
    return {'privacy':'PUBLIC','complexity':difficulty,'reason':'self_contained_public_question'}


def screen_payload(messages):
    """Hard outbound guard, including tool definitions and all conversation roles."""
    text = json.dumps(messages, ensure_ascii=False)
    if len(text.encode()) > 64000 or SECRET.search(text) or PRIVATE.search(text):
        raise ValueError('Cloud payload refused by local privacy policy.')
    return len(text.encode()) + 256  # conservative byte upper bound plus protocol allowance
