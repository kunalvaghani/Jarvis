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


MAX_ITEMS = 10000      # an array or object larger than this is rejected whole, never partially checked
MAX_NODES = 100000     # total values visited per validation; exceeding it rejects the whole value


def json_equal(left, right):
    """JSON equality: booleans are not numbers (false != 0, true != 1); 1 == 1.0; containers compare deeply."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is bool and type(right) is bool and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(json_equal(left[k], right[k]) for k in left)
    return type(left) is type(right) and left == right


def _within_size(value):
    """Count every node of the whole value (schema-independent), so unconstrained parts cannot exceed the budget."""
    stack, count = [value], 0
    while stack:
        item = stack.pop()
        count += 1
        if count > MAX_NODES:
            return False
        if isinstance(item, dict):
            if len(item) > MAX_ITEMS:
                return False
            stack.extend(item.values())
        elif isinstance(item, list):
            if len(item) > MAX_ITEMS:
                return False
            stack.extend(item)
    return True


def validate_schema_value(schema, value, path='arguments'):
    """Validate the entire value (every item) within fixed budgets; anything over budget is rejected, not sliced."""
    if not _within_size(value):
        raise ContractError(path + ' exceeds the validation budget; rejected as a whole.')
    _validate(schema, value, path, 0, [0])
    return True


def _validate(schema, value, path, depth, visited):
    visited[0] += 1
    if visited[0] > MAX_NODES:
        raise ContractError('Value exceeds the validation budget; rejected as a whole.')
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
    if 'enum' in schema:
        if not isinstance(schema['enum'], list) or not any(json_equal(value, option) for option in schema['enum']):
            raise ContractError(path + ' is not one of the allowed values.')
    if 'const' in schema and not json_equal(value, schema['const']):
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
        if len(value) > MAX_ITEMS:
            raise ContractError(path + ' has more items than can be validated; rejected as a whole.')
        if len(value) < schema.get('minItems', 0) or ('maxItems' in schema and len(value) > schema['maxItems']):
            raise ContractError(path + ' has an invalid number of items.')
        if 'items' in schema:
            for index, item in enumerate(value):  # every item, never a prefix
                _validate(schema['items'], item, path + '[' + str(index) + ']', depth + 1, visited)
    if isinstance(value, dict):
        if len(value) > MAX_ITEMS:
            raise ContractError(path + ' has more fields than can be validated; rejected as a whole.')
        properties = schema.get('properties', {})
        if not isinstance(properties, dict):
            raise ContractError('Unsupported properties at ' + path + '.')
        missing = [key for key in schema.get('required', []) if key not in value]
        if missing:
            raise ContractError(path + ' is missing required field(s): ' + ', '.join(missing)[:120])
        extra = schema.get('additionalProperties', True)
        for key, item in value.items():
            if key in properties:
                _validate(properties[key], item, path + '.' + str(key), depth + 1, visited)
            elif extra is False:
                raise ContractError(path + ' has an unexpected field: ' + str(key)[:60])
            elif isinstance(extra, dict):
                _validate(extra, item, path + '.' + str(key), depth + 1, visited)
            elif extra is not True:
                raise ContractError('Unsupported additionalProperties at ' + path + '.')


_OPTIONAL = {'annotations': dict, '_meta': dict}
BLOCK_FIELDS = {  # required fields per content block type (MCP 2025-11-25 content contract)
    'text': {'text': str}, 'image': {'data': str, 'mimeType': str}, 'audio': {'data': str, 'mimeType': str},
    'resource': {'resource': dict}, 'resource_link': {'uri': str, 'name': str}}
BLOCK_OPTIONAL = {'resource_link': {'title': str, 'description': str, 'mimeType': str, 'size': int}}
RESOURCE_OPTIONAL = {'mimeType': str, 'title': str, 'name': str, '_meta': dict, 'annotations': dict}


def _check_fields(container, required, optional, what):
    for field, kind in required.items():
        if not isinstance(container.get(field), kind) or isinstance(container.get(field), bool):
            raise ContractError('MCP ' + what + ' is missing a valid ' + field + '.')
    for field, kind in optional.items():
        if field in container and (not isinstance(container[field], kind) or isinstance(container[field], bool)):
            raise ContractError('MCP ' + what + ' has an invalid ' + field + '.')
    unexpected = set(container) - set(required) - set(optional) - {'type'}
    if unexpected:
        raise ContractError('MCP ' + what + ' has unsupported field(s): ' + ', '.join(sorted(unexpected))[:120])


def _check_embedded_resource(resource):
    """Embedded resource: a uri plus exactly one of text or (base64) blob, with typed optional fields."""
    bodies = [key for key in ('text', 'blob') if key in resource]
    if len(bodies) != 1:
        raise ContractError('MCP embedded resource needs exactly one of text or blob.')
    _check_fields(resource, {'uri': str, bodies[0]: str}, RESOURCE_OPTIONAL, 'embedded resource')
    if not resource['uri'].strip():
        raise ContractError('MCP embedded resource has an empty uri.')


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
        kind = block['type']
        _check_fields(block, BLOCK_FIELDS[kind], {**_OPTIONAL, **BLOCK_OPTIONAL.get(kind, {})}, kind + ' block')
        if kind == 'resource':
            _check_embedded_resource(block['resource'])
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
