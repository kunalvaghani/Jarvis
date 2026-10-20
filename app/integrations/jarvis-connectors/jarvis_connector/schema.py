"""Type hints -> JSON Schema, restricted to the subset Jarvis's bridge accepts.

Jarvis (``jarvis/mcp_contract.py``) refuses any tool whose schema uses keywords
outside a small subset (no ``anyOf``, ``$ref``, ``pattern``...). Connectors
therefore declare parameters with plain types plus an optional :class:`Param`,
and this module produces a schema that is always inside that subset. Anything
it cannot express is rejected when the connector class is defined, not at
call time.
"""
from dataclasses import dataclass
import inspect
import typing

SCALARS = {str: 'string', int: 'integer', float: 'number', bool: 'boolean'}


@dataclass(frozen=True)
class Param:
    """Optional constraints for one tool parameter: ``Annotated[str, Param(...)]``."""
    description: str = ''
    minimum: float = None
    maximum: float = None
    min_length: int = None
    max_length: int = None
    min_items: int = None
    max_items: int = None
    enum: tuple = None


class SchemaError(TypeError):
    """A tool signature that cannot be exposed safely; raised at class definition."""


def _unwrap(annotation):
    meta = None
    if typing.get_origin(annotation) is typing.Annotated:
        annotation, *extra = typing.get_args(annotation)
        meta = next((m for m in extra if isinstance(m, Param)), None)
    return annotation, meta


def type_schema(annotation, where):
    """Schema for a parameter/return type without constraints."""
    if annotation in SCALARS:
        return {'type': SCALARS[annotation]}
    if annotation in (dict, typing.Dict):
        return {'type': 'object'}
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is list:
        if len(args) != 1:
            raise SchemaError(where + ': list needs one item type, e.g. list[str].')
        return {'type': 'array', 'items': type_schema(args[0], where + '[]')}
    if origin is dict:
        if args and args[0] is not str:
            raise SchemaError(where + ': dict keys must be str.')
        return {'type': 'object'}
    raise SchemaError(where + ': unsupported type ' + repr(annotation)
                      + ' (use str, int, float, bool, list[...] or dict; Optional/Union are not supported).')


def _apply(schema, meta, where):
    if meta is None:
        return schema
    kind = schema['type']
    rules = {'minimum': meta.minimum, 'maximum': meta.maximum, 'minLength': meta.min_length,
             'maxLength': meta.max_length, 'minItems': meta.min_items, 'maxItems': meta.max_items}
    allowed = {'integer': {'minimum', 'maximum'}, 'number': {'minimum', 'maximum'},
               'string': {'minLength', 'maxLength'}, 'array': {'minItems', 'maxItems'}}.get(kind, set())
    for key, value in rules.items():
        if value is None:
            continue
        if key not in allowed:
            raise SchemaError(where + ': ' + key + ' does not apply to ' + kind + '.')
        schema[key] = value
    if meta.enum is not None:
        schema['enum'] = list(meta.enum)
    if meta.description:
        schema['description'] = meta.description
    return schema


@dataclass
class ParamSpec:
    name: str
    schema: dict
    required: bool
    default: object = None


def parameters(function, where):
    """Inspect a tool method (excluding ``self``) and return ``(param specs, input schema)``."""
    hints = typing.get_type_hints(function, include_extras=True)
    specs, properties, required = [], {}, []
    for name, parameter in list(inspect.signature(function).parameters.items())[1:]:
        if parameter.kind not in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY):
            raise SchemaError(where + ': *args/**kwargs are not allowed in tools.')
        if name not in hints:
            raise SchemaError(where + ': parameter ' + name + ' needs a type hint.')
        annotation, meta = _unwrap(hints[name])
        schema = _apply(type_schema(annotation, where + '.' + name), meta, where + '.' + name)
        has_default = parameter.default is not parameter.empty
        if has_default:
            if parameter.default is None:
                raise SchemaError(where + '.' + name + ': None defaults are not supported; use a typed default.')
            schema['default'] = parameter.default
        else:
            required.append(name)
        properties[name] = schema
        specs.append(ParamSpec(name, schema, not has_default, parameter.default if has_default else None))
    schema = {'type': 'object', 'properties': properties, 'additionalProperties': False}
    if required:
        schema['required'] = required
    return specs, schema


def output_schema(function, where):
    """Wrap the return type as ``{"result": ...}`` (the MCP structured-content convention)."""
    hints = typing.get_type_hints(function, include_extras=True)
    if 'return' not in hints:
        raise SchemaError(where + ': tools must declare a return type.')
    result = type_schema(_unwrap(hints['return'])[0], where + '->')
    return {'type': 'object', 'properties': {'result': result}, 'required': ['result']}


def _matches(schema, value):
    kind = schema.get('type')
    if kind == 'integer':
        return type(value) is int
    if kind == 'number':
        return type(value) in (int, float)
    if kind == 'boolean':
        return type(value) is bool
    if kind == 'string':
        return isinstance(value, str)
    if kind == 'array':
        return isinstance(value, list)
    if kind == 'object':
        return isinstance(value, dict)
    return False


def check_value(schema, value, where):
    """Validate one argument; returns an error message or ``None``. Never coerces."""
    if not _matches(schema, value):
        return where + ' must be ' + schema['type'] + '.'
    if 'enum' in schema and value not in schema['enum']:
        return where + ' must be one of ' + ', '.join(map(str, schema['enum']))[:200] + '.'
    if type(value) in (int, float):
        if 'minimum' in schema and value < schema['minimum'] or 'maximum' in schema and value > schema['maximum']:
            return where + ' must be between ' + str(schema.get('minimum', '-inf')) + ' and ' + str(schema.get('maximum', 'inf')) + '.'
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or len(value) > schema.get('maxLength', len(value)):
            return where + ' has an invalid length.'
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', len(value)):
            return where + ' has an invalid number of items.'
        for index, item in enumerate(value):
            problem = check_value(schema['items'], item, where + '[' + str(index) + ']')
            if problem:
                return problem
    return None
