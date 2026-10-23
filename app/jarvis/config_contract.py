"""Shallow startup contract. Unknown fields warn without granting new permissions."""
import warnings
import json
from pathlib import Path

OBJECT_FIELDS = frozenset('task_queue voice knowledge_acquisition groq gpu_scheduler realtime context_selector command_cleanup anticipation ui agent_runtime whisper cursor push_to_write apps folders files knowledge memory weather cognition gods_eye repo_learning weather_alerts whatsapp media speech brain documents repo_abilities repository_skills rea deliberation self_evolution docker_runtime execution_strategy reasoning_bank viking_memory exploration cloud_architect demonstration evolution_lab awareness project_intelligence'.split())
OBJECT_FIELDS = OBJECT_FIELDS | {'engineering_judgment'}
KNOWN_FIELDS = OBJECT_FIELDS | frozenset({'model_path','files_root','project_roots','microphone',
    'wake_timeout_seconds','suggestion_seconds','file_catalog','_ui_verification'})
MAX_ROOT_FIELDS = 128
MAX_CONFIG_BYTES = 2_000_000

class ConfigurationWarning(UserWarning):
    """Metadata-only diagnostic for unsupported root fields."""

def load_config(path):
    """Bound bytes before decoding; malformed/deep JSON produces a private-safe error."""
    try:
        with Path(path).open('rb') as stream:
            raw=stream.read(MAX_CONFIG_BYTES+1)
        if len(raw)>MAX_CONFIG_BYTES:
            raise ValueError('Jarvis configuration exceeds the two-million-byte limit.')
        def invalid_constant(_):raise ValueError('Non-finite JSON configuration number.')
        value=json.loads(raw.decode('utf-8'),parse_constant=invalid_constant)
    except (UnicodeError,RecursionError,json.JSONDecodeError) as exc:
        raise ValueError('Malformed or excessively nested Jarvis configuration.') from None
    return validate_root(value)

def validate_root(config):
    if not isinstance(config,dict) or len(config)>MAX_ROOT_FIELDS or any(not isinstance(k,str) or len(k)>128 for k in config):
        raise ValueError('Jarvis configuration must be a bounded object with string field names.')
    if any(not isinstance(config[key],dict) for key in OBJECT_FIELDS if key in config):
        raise ValueError('Jarvis configuration sections must be objects.')
    pending=[(config,0)];count=0
    while pending:
        item,depth=pending.pop();count+=1
        if depth>32 or count>100000:
            raise ValueError('Jarvis configuration nesting or item limit exceeded.')
        if isinstance(item,dict):pending.extend((value,depth+1) for value in item.values())
        elif isinstance(item,list):pending.extend((value,depth+1) for value in item)
    unknown=set(config)-KNOWN_FIELDS
    if unknown:
        # Never echo values or unknown names: either may contain a pasted secret.
        warnings.warn('Unknown top-level Jarvis configuration fields: '+str(len(unknown))+
            '. They are not a permission grant; check the documented configuration.',ConfigurationWarning,stacklevel=2)
    if 'engineering_judgment' in config:
        from .engineering_judgment import settings
        settings(config['engineering_judgment'])
    return config
