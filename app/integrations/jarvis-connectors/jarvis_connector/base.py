"""BaseConnector: the parent class every Jarvis MCP connector inherits from.

A child connector only declares tools::

    class NotesConnector(BaseConnector):
        name = 'jarvis-notes'

        @tool()
        def search_notes(self, query: Annotated[str, Param(min_length=1, max_length=120)]) -> list[dict]:
            '''Search approved notes.'''
            ...

    if __name__ == '__main__':
        NotesConnector.main()

The base supplies what every connector needs and should not re-implement:
schemas Jarvis accepts, argument validation (no coercion), read/write access
policy, bounded results, typed tool errors that never leak tracebacks, CLI
configuration (Jarvis forwards arguments, not secret environment values) and
the stdio runtime (official MCP SDK v2 ``MCPServer`` when installed, otherwise
a dependency-free built-in implementation of the same protocol subset).
"""
import argparse
from dataclasses import dataclass
import json
import re
import sys
import traceback

from . import schema as schemas

TOOL_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,63}')
ACCESS = ('read', 'write')


class ToolError(Exception):
    """An expected failure. Its message is returned to Jarvis as an ``isError`` result."""


class UnknownTool(LookupError):
    """The requested tool does not exist or is not exposed (e.g. a write tool without --allow-write)."""


def tool(name=None, *, access='read', destructive=False, idempotent=None):
    """Mark a connector method as an MCP tool.

    ``access='write'`` tools change external state. They are hidden and
    uncallable unless the connector is started with ``--allow-write``; Jarvis
    still asks for approval on every call. ``destructive`` marks writes that
    delete or overwrite data.
    """
    if callable(name):  # bare @tool
        return tool()(name)
    if access not in ACCESS:
        raise ValueError('access must be "read" or "write".')

    def mark(function):
        function.__jarvis_tool__ = {'name': name or function.__name__, 'access': access,
                                    'destructive': bool(destructive and access == 'write'),
                                    'idempotent': (access == 'read') if idempotent is None else bool(idempotent)}
        return function
    return mark


@dataclass
class ToolSpec:
    name: str
    method: str
    description: str
    access: str
    destructive: bool
    idempotent: bool
    params: list
    input_schema: dict
    output_schema: dict

    def describe(self):
        """The MCP ``tools/list`` row for this tool."""
        return {'name': self.name, 'description': self.description, 'inputSchema': self.input_schema,
                'outputSchema': self.output_schema,
                'annotations': {'readOnlyHint': self.access == 'read', 'destructiveHint': self.destructive,
                                'idempotentHint': self.idempotent, 'openWorldHint': False}}


class BaseConnector:
    #: MCP server name reported to Jarvis (required in every child).
    name = ''
    version = '0.1.0'
    #: Optional guidance the server reports at initialize.
    instructions = ''
    #: Limit for the whole MCP result as Jarvis receives it. The value appears twice (text block and
    #: structuredContent, the text JSON-escaped again) and Jarvis's bridge truncates at 10,000
    #: characters, so anything larger would reach Jarvis as cut, invalid JSON. Oversized results
    #: fail with a ToolError instead; use ``fits`` to trim lists before returning.
    max_result_chars = 9500

    _specs = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        found = {}
        for klass in reversed(cls.__mro__):
            for attribute, value in vars(klass).items():
                marker = getattr(value, '__jarvis_tool__', None)
                if marker is None:
                    found = {k: v for k, v in found.items() if v.method != attribute}
                    continue
                where = cls.__name__ + '.' + attribute
                if not TOOL_NAME.fullmatch(marker['name']):
                    raise schemas.SchemaError(where + ': tool names must match ' + TOOL_NAME.pattern)
                description = ' '.join((value.__doc__ or '').split())
                if not description:
                    raise schemas.SchemaError(where + ': a docstring is required; Jarvis shows it to the model.')
                params, input_schema = schemas.parameters(value, where)
                found = {k: v for k, v in found.items() if v.method != attribute}
                if marker['name'] in found:
                    raise schemas.SchemaError(where + ': duplicate tool name ' + marker['name'])
                found[marker['name']] = ToolSpec(
                    marker['name'], attribute, description, marker['access'], marker['destructive'],
                    marker['idempotent'], params, input_schema, schemas.output_schema(value, where))
        cls._specs = found

    def __init__(self, allow_write=False):
        if not self.name:
            raise TypeError(type(self).__name__ + ' must set a non-empty name.')
        self.allow_write = allow_write

    # ----- hooks for children -------------------------------------------------
    @classmethod
    def add_arguments(cls, parser):
        """Add connector-specific command-line options (paths, hosts...). Never accept secret values here."""

    def configure(self, options):
        """Apply parsed options. Keep it cheap and non-failing; validate lazily inside tools."""

    # ----- catalog and dispatch -----------------------------------------------
    def tools(self):
        return [spec for spec in self._specs.values() if spec.access == 'read' or self.allow_write]

    def describe(self):
        return [spec.describe() for spec in self.tools()]

    def spec(self, name):
        spec = self._specs.get(name)
        if spec is None or (spec.access == 'write' and not self.allow_write):
            raise UnknownTool(name)
        return spec

    def validate(self, spec, arguments):
        """Return complete keyword arguments, or raise ToolError. Values are never coerced."""
        if not isinstance(arguments, dict):
            raise ToolError('Arguments must be an object.')
        known = {p.name for p in spec.params}
        extra = sorted(set(arguments) - known)
        if extra:
            raise ToolError('Unexpected argument(s): ' + ', '.join(extra)[:200])
        values = {}
        for param in spec.params:
            if param.name not in arguments:
                if param.required:
                    raise ToolError('Missing required argument: ' + param.name)
                values[param.name] = param.default
                continue
            problem = schemas.check_value(param.schema, arguments[param.name], param.name)
            if problem:
                raise ToolError(problem)
            values[param.name] = arguments[param.name]
        return values

    def invoke(self, name, arguments):
        """Validate and run one tool, returning its Python value. Raises UnknownTool or ToolError."""
        spec = self.spec(name)
        values = self.validate(spec, arguments)
        try:
            value = getattr(self, spec.method)(**values)
        except ToolError:
            raise
        except Exception:
            traceback.print_exc(file=sys.stderr)
            raise ToolError('Internal error in ' + name + '; see the connector log.') from None
        problem = schemas.check_value(spec.output_schema['properties']['result'], value, name + ' result')
        if problem:
            print('Connector bug: ' + problem, file=sys.stderr)
            raise ToolError('Internal error in ' + name + ': result did not match its declared type.')
        try:
            size = self.result_size(value)
        except (TypeError, ValueError):
            raise ToolError('Internal error in ' + name + ': result is not JSON-serializable.') from None
        if size > self.max_result_chars:
            raise ToolError('Result is too large (' + str(size) + ' characters); narrow the request.')
        return value

    @staticmethod
    def result_size(value):
        """Characters of the MCP result Jarvis receives for ``value`` (see ``call``)."""
        return len(json.dumps(BaseConnector._result(value), ensure_ascii=False))

    def fits(self, value):
        """True when ``value`` can be returned without exceeding ``max_result_chars``."""
        return self.result_size(value) <= self.max_result_chars

    @staticmethod
    def _result(value):
        return {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False)}],
                'structuredContent': {'result': value}, 'isError': False}

    def call(self, name, arguments):
        """Run a tool and return an MCP ``tools/call`` result. Raises UnknownTool only."""
        try:
            value = self.invoke(name, arguments)
        except ToolError as exc:
            return {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True}
        return self._result(value)

    # ----- entry point --------------------------------------------------------
    @classmethod
    def main(cls, argv=None):
        parser = argparse.ArgumentParser(prog=cls.name or cls.__name__, description=cls.__doc__)
        parser.add_argument('--runtime', choices=('auto', 'sdk', 'builtin'), default='auto',
                            help='auto: official MCP SDK v2 if installed, else the built-in stdio runtime.')
        parser.add_argument('--allow-write', action='store_true',
                            help='Expose write tools. Jarvis still approves each call.')
        parser.add_argument('--list-tools', action='store_true',
                            help='Print the tool catalog as JSON and exit (no MCP session).')
        cls.add_arguments(parser)
        options = parser.parse_args(argv)
        connector = cls(allow_write=options.allow_write)
        connector.configure(options)
        if options.list_tools:
            print(json.dumps(connector.describe(), indent=2))
            return 0
        from . import sdk_runtime, stdio_runtime
        runtime = options.runtime
        if runtime == 'auto':
            runtime = 'sdk' if sdk_runtime.available() else 'builtin'
        if runtime == 'sdk':
            if not sdk_runtime.available():
                parser.error('--runtime sdk needs the official MCP Python SDK v2 (pip install -r requirements.txt).')
            sdk_runtime.run(connector)
        else:
            stdio_runtime.run(connector)
        return 0
