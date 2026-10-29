"""Explicit project consent and free-only cloud coding configuration."""
import hashlib
import json
import os
from pathlib import Path
import re
from .cloud_policy import SECRET, KEY_MATERIAL, privacy_text

GEMINI_MODEL='gemini-3.8-flash'
GEMINI_DEFAULTS=dict(enabled=True,model=GEMINI_MODEL,api_project_id='',quota_project_id='',quota_model_id=GEMINI_MODEL,
    quota_verified=False,key_project_confirmed=False,billing_disabled_confirmed=False,free_tier_confirmed=False,
    account_plan='unknown',free_only=True,quota_key_sha256='',max_minute_requests=5,max_daily_requests=20,
    max_minute_input_tokens=250000,max_minute_tokens=None,max_daily_tokens=None,safety_margin=.2,
    daily_reset='America/Los_Angeles',max_concurrent_calls=1,max_task_calls=3,max_output_tokens=8192,
    timeout_seconds=90,thinking='low',api_protocol='interactions',quota_source='user_reported_pending_project_binding')
CODING_DEFAULTS=dict(enabled=False,dry_run_verified=False,preference='auto',max_task_cloud_calls=8,
    groq_max_output_tokens=1024,gemini_max_task_calls=3,repair_escalation_after=2)


class ContextBudgetExceeded(ValueError):
    def __init__(self,messages,maximum):
        super().__init__('cloud_context_budget_exceeded')
        self.details={'model_text_bytes':sum(len(row['content'].encode()) for row in messages),
                      'maximum_model_text_bytes':maximum,'section_bytes':[len(row['content'].encode()) for row in messages]}


def gemini_settings(value=None):
    if value is not None and (not isinstance(value,dict) or set(value)-set(GEMINI_DEFAULTS)):raise ValueError('Unknown Gemini setting.')
    result={**GEMINI_DEFAULTS,**(value or {})}
    for key,default in GEMINI_DEFAULTS.items():
        if type(default) is bool and type(result[key]) is not bool:raise ValueError('Invalid Gemini boolean: '+key)
    for key,maximum in [('max_minute_requests',5),('max_daily_requests',20),('max_minute_input_tokens',250000),
                        ('max_concurrent_calls',1),('max_task_calls',16),('max_output_tokens',8192),('timeout_seconds',120)]:
        if type(result[key]) is not int or not 1<=result[key]<=maximum:raise ValueError('Invalid Gemini limit: '+key)
    if type(result['safety_margin']) not in (int,float) or not .2<=result['safety_margin']<=.5:raise ValueError('Gemini requires at least20 percent headroom.')
    if result['model']!=GEMINI_MODEL or result['quota_model_id']!=GEMINI_MODEL:raise ValueError('Gemini model/quota binding mismatch.')
    if result['max_daily_tokens'] is not None or result['max_minute_tokens'] is not None:raise ValueError('No Gemini daily/combined token quota was provided.')
    if result['daily_reset']!='America/Los_Angeles' or not result['free_only']:raise ValueError('Unsupported Gemini billing/reset policy.')
    if result['account_plan'] not in ('unknown','free','paid') or result['thinking'] not in ('low','medium','high'):raise ValueError('Invalid Gemini account/thinking mode.')
    if result['api_protocol'] not in ('interactions','generate_content'):raise ValueError('Unsupported Gemini API protocol.')
    for key in ('api_project_id','quota_project_id'):
        if not isinstance(result[key],str) or result[key] and not re.fullmatch(r'[a-z][a-z0-9-]{4,62}',result[key]):raise ValueError('Invalid Gemini project ID.')
    if not isinstance(result['quota_key_sha256'],str) or result['quota_key_sha256'] and not re.fullmatch('[a-f0-9]{64}',result['quota_key_sha256']):raise ValueError('Invalid key binding fingerprint.')
    return result


def coding_settings(value=None):
    if value is not None and (not isinstance(value,dict) or set(value)-set(CODING_DEFAULTS)):raise ValueError('Unknown cloud coding setting.')
    result={**CODING_DEFAULTS,**(value or {})}
    for key in ('enabled','dry_run_verified'):
        if type(result[key]) is not bool:raise ValueError('Invalid cloud coding boolean.')
    if result['preference'] not in ('auto','local','groq','gemini'):raise ValueError('Unknown coding provider preference.')
    for key,maximum in [('max_task_cloud_calls',16),('groq_max_output_tokens',4096),('gemini_max_task_calls',16),('repair_escalation_after',6)]:
        if type(result[key]) is not int or not 1<=result[key]<=maximum:raise ValueError('Invalid cloud coding bound.')
    return result


def credential(base):
    value=os.environ.get('GEMINI_API_KEY')
    if not value:
        path=Path(base)/'secrets/gemini.json'
        if not path.exists():return None
        if any(p.is_symlink() or hasattr(p,'is_junction') and p.is_junction() for p in (path,path.parent)) or path.stat().st_size>8192:raise ValueError('Unsupported Gemini credential file.')
        value=json.loads(path.read_text(encoding='utf-8')).get('GEMINI_API_KEY')
    if not isinstance(value,str) or not 10<=len(value)<=300 or any(c.isspace() for c in value):raise ValueError('Invalid Gemini credential format.')
    return value


def gemini_eligible(options,key):
    if not key:return 'missing_api_key'
    if not options['enabled']:return 'provider_disabled'
    if options['account_plan']!='free' or not options['free_tier_confirmed'] or not options['billing_disabled_confirmed']:return 'free_account_unverified'
    if (not options['quota_verified'] or not options['key_project_confirmed'] or not options['api_project_id']
            or options['api_project_id']!=options['quota_project_id'] or options['quota_model_id']!=options['model']
            or options['quota_key_sha256']!=hashlib.sha256(key.encode()).hexdigest()):return 'quota_unverified'
    return None


def approved_payload(messages,context,*,maximum=64000):
    """Only trusted per-task provenance permits source. Secret-bearing data is refused."""
    if not isinstance(context,dict) or context.get('provenance') not in ('synthetic','explicitly_approved') or context.get('restricted') is not False:
        raise ValueError('cloud_project_not_approved')
    if not isinstance(messages,list) or not messages or len(messages)>64:raise ValueError('invalid_coding_messages')
    result=[]
    for message in messages:
        if set(message)-{'role','content'} or message.get('role') not in ('system','user','assistant') or not isinstance(message.get('content'),str):raise ValueError('unsupported_coding_message')
        text=privacy_text(message['content'])
        if SECRET.search(text) or re.search(r'(?i)(?<!\w)(?:\.env\b|id_rsa\b|credentials\.json\b|secrets[\\/])',text):raise ValueError('coding_secret_refused')
        # Host filesystem paths never leave the machine. Relative project paths
        # and source hashes remain available to the same local tool dispatcher.
        text=re.sub(r'(?i)(?:[a-z]:[\\/]|/(?:home|users)/)[^\r\n"<>]+',lambda m:m[0].replace('\\','/').rstrip('/').split('/')[-1],text)
        if re.search(r'(?i)[a-z]:[\\/]|\\\\[a-z0-9_.-]+[\\/]',text):raise ValueError('unredacted_host_path')
        result.append({'role':message['role'],'content':text})
    if sum(len(row['content'].encode()) for row in result)>maximum:raise ContextBudgetExceeded(result,maximum)
    return result


def token_estimate(payload):
    """Conservative practical estimate, not an exact tokenizer or provider balance.

    Three decoded UTF-8 bytes per projected token remains conservative against
    the first metered Groq request (1906 input tokens vs5044 previously reserved).
    It is a heuristic, not a tokenizer guarantee or a quality comparison.
    Metered usage replaces it; underestimated Groq reservations trigger the
    existing durable overrun pause. The extra20 percent is separate headroom.
    """
    if isinstance(payload,dict) and isinstance(payload.get('messages'),list):
        messages=payload['messages']
        size=sum(len(row.get('content','').encode()) for row in messages)
        size+=len(json.dumps(payload.get('tools',[]),ensure_ascii=False,separators=(',',':')).encode())
        return (size+2)//3+256+12*len(messages)
    size=len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())
    return (size+1)//2+256
