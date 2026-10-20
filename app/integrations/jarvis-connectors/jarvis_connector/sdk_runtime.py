"""Serve a BaseConnector through the official MCP Python SDK v2 (``mcp.server.MCPServer``).

Requires ``mcp>=2,<3`` (Python 3.11+). Do not mix with SDK v1's ``FastMCP``.
Each connector tool is registered as a keyword-only function whose signature
mirrors the declared parameters, so the SDK derives the same schema; the call
itself still goes through ``BaseConnector.invoke`` so validation, access policy
and result bounds are identical in both runtimes.
"""
import inspect
import typing


def available():
    try:
        from mcp.server import MCPServer  # noqa: F401  (v2 only; v1 has FastMCP instead)
    except ImportError:
        return False
    return True


def _sdk_tool_error():
    for module in ('mcp.server.mcpserver.exceptions', 'mcp.server.exceptions'):
        try:
            return __import__(module, fromlist=['ToolError']).ToolError
        except (ImportError, AttributeError):
            continue
    return RuntimeError


def _annotation(param):
    from pydantic import Field  # an SDK dependency
    schema = param.schema
    base = {'string': str, 'integer': int, 'number': float, 'boolean': bool, 'object': dict}.get(schema['type'])
    if schema['type'] == 'array':
        item = {'string': str, 'integer': int, 'number': float, 'boolean': bool, 'object': dict}[schema['items']['type']]
        base = list[item]
    if 'enum' in schema:
        base = typing.Literal[tuple(schema['enum'])]
    limits = {'description': schema.get('description'), 'ge': schema.get('minimum'), 'le': schema.get('maximum'),
              'min_length': schema.get('minLength', schema.get('minItems')),
              'max_length': schema.get('maxLength', schema.get('maxItems'))}
    return typing.Annotated[base, Field(**{k: v for k, v in limits.items() if v is not None})]


def _handler(connector, spec, sdk_error):
    def handler(**arguments):
        from .base import ToolError
        try:
            return connector.invoke(spec.name, arguments)
        except ToolError as exc:
            raise sdk_error(str(exc)) from None

    method = getattr(type(connector), spec.method)
    returns = typing.get_type_hints(method).get('return', inspect.Signature.empty)
    parameters = [inspect.Parameter(p.name, inspect.Parameter.KEYWORD_ONLY, annotation=_annotation(p),
                                    default=inspect.Parameter.empty if p.required else p.default)
                  for p in spec.params]
    handler.__signature__ = inspect.Signature(parameters, return_annotation=returns)
    handler.__annotations__ = {**{p.name: p.annotation for p in parameters}, 'return': returns}
    handler.__name__ = handler.__qualname__ = spec.name
    handler.__doc__ = spec.description
    return handler


def run(connector):
    from mcp.server import MCPServer
    server = MCPServer(connector.name, instructions=connector.instructions or None)
    sdk_error = _sdk_tool_error()
    for spec in connector.tools():
        register = server.tool(name=spec.name, description=spec.description)
        register(_handler(connector, spec, sdk_error))
    server.run()  # stdio transport; Jarvis launches the connector as a subprocess
