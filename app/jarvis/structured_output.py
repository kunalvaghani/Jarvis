"""Strict local model boundaries. Evidence is local; malformed text is never repaired by guessing."""
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4


class ModelOutputError(ValueError):
    """Read-only inference may be regenerated; no proposed action was executed."""


def generation_schema(schema):
    """Backend-safe grammar copy; the original remains the decode contract.

    The installed backend's regex conversion admitted JSON delimiters in a
    negated string pattern. Ordinary JSON strings passed the paired control.
    Omit regex keywords from generation only; types, closed properties, enums
    and size bounds remain. Strict local decoding still enforces every regex.
    Property names (including a field literally named pattern) are data.
    """
    import copy
    result={}
    for key,value in schema.items():
        if key=='pattern':continue
        if key in {'properties','patternProperties','$defs','definitions'}:
            result[key]={name:generation_schema(child) for name,child in value.items()}
        elif key in {'items','additionalProperties','not','if','then','else','contains'} and isinstance(value,dict):
            result[key]=generation_schema(value)
        elif key in {'anyOf','oneOf','allOf','prefixItems'}:
            result[key]=[generation_schema(child) for child in value]
        else:result[key]=copy.deepcopy(value)
    return result


def validate_contract(schema, value, path='proposal', depth=0):
    """Model schemas add unions/patterns to the existing bounded validator.

    This does not broaden the separate MCP security contract's schema subset.
    """
    from .mcp_contract import validate_schema_value
    if depth>16:raise ValueError('Model contract nesting exceeds limit.')
    if 'anyOf' in schema:
        errors=[]
        branches=schema['anyOf']
        discriminator=next((key for key in ('tool','kind') if isinstance(value,dict) and isinstance(value.get(key),str)),None)
        if discriminator:
            compatible=[branch for branch in branches if
                branch.get('properties',{}).get(discriminator,{}).get('enum') is None or
                value[discriminator] in branch['properties'][discriminator]['enum']]
            if compatible:branches=compatible  # Other discriminated branches cannot match.
        for branch in branches:
            try:
                validate_contract(branch,value,path,depth+1)
                break
            except ValueError as error:errors.append(str(error))
        else:raise ValueError(path+' matches no allowed contract: '+'; '.join(errors)[:1000])
    if 'pattern' in schema and isinstance(value,str) and not re.search(schema['pattern'],value):
        label='required path format' if path.endswith(('.path','.file_path')) else 'required string pattern'
        raise ValueError(path+' does not match the '+label+'; received '+repr(value)[:160]+'.')
    shallow={k:v for k,v in schema.items() if k not in {'anyOf','pattern','properties','items'}}
    if 'properties' in schema:shallow['properties']={k:{} for k in schema['properties']}
    if 'items' in schema:shallow['items']={}
    validate_schema_value(shallow,value,path)
    if isinstance(value,dict):
        for key,child in schema.get('properties',{}).items():
            if key in value:validate_contract(child,value[key],path+'.'+key,depth+1)
    if isinstance(value,list) and 'items' in schema:
        for index,child in enumerate(value):validate_contract(schema['items'],child,path+'['+str(index)+']',depth+1)


def preserve(directory, stage, raw, metadata, error=None):
    """Keep bounded original response text and exact diagnostics, including the final attempt."""
    if directory is None:
        return None
    target = Path(directory) / 'model-responses' / (stage + '-' + uuid4().hex)
    target.mkdir(parents=True)
    data = raw.encode('utf-8')
    (target / 'response.txt').write_bytes(data)
    record = {'date': datetime.now(timezone.utc).isoformat(), 'stage': stage,
              'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), **metadata}
    if error is not None:
        record.update(error_type=type(error).__name__, error=str(error))
        if isinstance(error, json.JSONDecodeError):
            record.update(line=error.lineno, column=error.colno, character=error.pos,
                          surrounding=raw[max(0, error.pos-100):error.pos+100])
    (target / 'metadata.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return str(target)


def decode(raw, *, completed, reason=None, schema=None, directory=None, stage='proposal', metadata=None):
    """Require completion, strict JSON and an explicit typed contract before dispatch."""
    details = {**(metadata or {}), 'completed': completed, 'done_reason': reason}
    value=None
    try:
        if not completed or reason in {'length', 'max_tokens', 'cancelled', 'canceled'}:
            raise ModelOutputError('Incomplete model output (' + str(reason) + '); no proposal executed. Regenerate a smaller response.')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ModelOutputError('Model proposal must be a JSON object; no proposal executed.')
        if schema is not None:
            validate_contract(schema, value, stage)
        arguments=value.get('arguments')
        if stage=='tool' and value.get('tool')=='Edit' and isinstance(arguments,dict) and (
                isinstance(arguments.get('old_string'),str) and arguments.get('old_string')==arguments.get('new_string')):
            raise ModelOutputError('Edit old_string and new_string are identical; no change was proposed and no action executed. Choose a materially different correction, or use run_checks to observe the current source.')
    except (ValueError, TypeError, RecursionError) as exc:
        evidence = preserve(directory, stage, raw, details, exc)
        error=ModelOutputError(str(exc) + (' Evidence: ' + evidence if evidence else ''))
        if isinstance(value,dict):error.previous_proposal=value  # Rejected diagnostic data, never executable.
        raise error from exc
    preserve(directory, stage, raw, details)
    return value
