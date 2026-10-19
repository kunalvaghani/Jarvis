"""MCP call contract checks (Prompt 33: P33-002 arguments, P33-003 results, P33-001 schema pinning).

* ``validate_schema_value``: a bounded, explicit JSON-Schema subset. Constraining keywords outside the
  subset make the schema *unsupported* and the call is refused (nothing is guessed). Annotation-only
  keywords are ignored.
* ``validate_result``: the MCP ``tools/call`` result envelope (content blocks, isError, structuredContent)
  and, when the tool advertised one, its output schema.
* ``schema_digest``: a canonical digest of a tool's advertised input/output schemas, pinned for generated
  servers so a changed contract is treated as drift.
"""
import hashlib
import json

ANNOTATIONS = {'title', 'description', 'default', 'examples', '$schema', '$comment', 'format', 'readOnly',
               'writeOnly', 'deprecated'}
SUPPORTED = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum', 'const', 'minimum',
             'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'minLength', 'maxLength', 'minItems', 'maxItems'}
TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}
MAX_DEPTH = 8


class ContractError(ValueError):
    """Typed contract failure; a ValueError so existing no-retry handling applies unchanged."""


def _type_ok(name, value):
    if name == 'integer':
        return type(value) is int
    if name == 'number':
        return type(value) in (int, float)
    return isinstance(value, TYPES[name]) and not (name in {'object', 'array', 'string'} and isinstance(value, bool))


def validate_schema_value(schema, value, path='arguments', depth=0):
    if depth > MAX_DEPTH:
        raise ContractError('Schema nesting exceeds the supported depth.')
    if not isinstance(schema, dict):
        raise ContractError('Unsupported schema at ' + path + '.')
    unknown = {k for k in schema if k not in SUPPORTED and k not in ANNOTATIONS and not k.startswith('x-')}
    if unknown:
        raise ContractError('Unsupported schema keyword(s) at ' + path + ': ' + ', '.join(sorted(unknown))[:120])
    kind = schema.get('type')
    if kind is not None:
        kinds = kind if isinstance(kind, list) else [kind]
        if not kinds or any(k not in {'object', 'array', 'string', 'integer', 'number', 'boolean', 'null'} for k in kinds):
            raise ContractError('Unsupported schema type at ' + path + '.')
        if not any(_type_ok(k, value) for k in kinds):
            raise ContractError(path + ' must be ' + '/'.join(kinds) + '.')
    if 'enum' in schema and value not in schema['enum']:
        raise ContractError(path + ' is not one of the allowed values.')
    if 'const' in schema and value != schema['const']:
        raise ContractError(path + ' does not match the required constant.')
    if type(value) in (int, float):
        for key, ok in (('minimum', lambda b: value >= b), ('maximum', lambda b: value <= b),
                        ('exclusiveMinimum', lambda b: value > b), ('exclusiveMaximum', lambda b: value < b)):
            if key in schema and not ok(schema[key]):
                raise ContractError(path + ' is outside its allowed range.')
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or ('maxLength' in schema and len(value) > schema['maxLength']):
            raise ContractError(path + ' has an invalid length.')
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or ('maxItems' in schema and len(value) > schema['maxItems']):
            raise ContractError(path + ' has an invalid number of items.')
        if 'items' in schema:
            for index, item in enumerate(value[:1000]):
                validate_schema_value(schema['items'], item, f'{path}[{index}]', depth + 1)
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        if not isinstance(properties, dict):
            raise ContractError('Unsupported properties at ' + path + '.')
        missing = [key for key in schema.get('required', []) if key not in value]
        if missing:
            raise ContractError(path + ' is missing required field(s): ' + ', '.join(missing)[:120])
        extra = schema.get('additionalProperties', True)
        for key, item in value.items():
            if key in properties:
                validate_schema_value(properties[key], item, path + '.' + str(key), depth + 1)
            elif extra is False:
                raise ContractError(path + ' has an unexpected field: ' + str(key)[:60])
            elif isinstance(extra, dict):
                validate_schema_value(extra, item, path + '.' + str(key), depth + 1)
            elif extra is not True:
                raise ContractError('Unsupported additionalProperties at ' + path + '.')
    return True


BLOCK_FIELDS = {'text': {'text': str}, 'image': {'data': str, 'mimeType': str}, 'audio': {'data': str, 'mimeType': str},
                'resource': {'resource': dict}, 'resource_link': {'uri': str, 'name': str}}


def validate_result(result, output_schema=None):
    """Raise ContractError for a malformed tools/call result; never repair or reinterpret it."""
    if not isinstance(result, dict):
        raise ContractError('MCP result is not an object.')
    if 'isError' in result and type(result['isError']) is not bool:
        raise ContractError('MCP result isError must be a boolean.')
    content = result.get('content')
    if not isinstance(content, list) or len(content) > 200:
        raise ContractError('MCP result content must be a list of content blocks.')
    for block in content:
        if not isinstance(block, dict) or block.get('type') not in BLOCK_FIELDS:
            raise ContractError('MCP result has an unsupported content block.')
        for field, kind in BLOCK_FIELDS[block['type']].items():
            if not isinstance(block.get(field), kind):
                raise ContractError('MCP ' + block['type'] + ' block is missing a valid ' + field + '.')
    if 'structuredContent' in result and not isinstance(result['structuredContent'], dict):
        raise ContractError('MCP structuredContent must be an object.')
    if output_schema is not None and result.get('isError') is not True:
        if 'structuredContent' not in result:
            raise ContractError('Tool declared an output schema but returned no structuredContent.')
        validate_schema_value(output_schema, result['structuredContent'], 'structuredContent')
    return result


def schema_digest(tool):
    canonical = json.dumps({'input': tool.get('inputSchema'), 'output': tool.get('outputSchema')}, sort_keys=True,
                           separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
