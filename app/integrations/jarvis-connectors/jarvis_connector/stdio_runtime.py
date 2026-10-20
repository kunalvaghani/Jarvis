"""Dependency-free MCP stdio server for a BaseConnector (tools only).

Implements the subset Jarvis's bridge uses: newline-delimited JSON-RPC 2.0 with
``initialize``, ``notifications/initialized``, ``ping``, ``tools/list`` and
``tools/call``. No resources, prompts, sampling, logging or batching.
Anything a tool prints is redirected to stderr so it cannot corrupt the protocol.
"""
import json
import sys

SUPPORTED = ('2025-11-25', '2025-06-18', '2025-03-26')
MAX_LINE = 1024 * 1024

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602


def _error(identifier, code, message):
    return {'jsonrpc': '2.0', 'id': identifier, 'error': {'code': code, 'message': message}}


def handle(connector, message):
    """Return the JSON-RPC response for one decoded message, or ``None`` for notifications."""
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or not isinstance(message.get('method'), str):
        return _error(message.get('id') if isinstance(message, dict) else None, INVALID_REQUEST, 'Invalid request')
    if 'id' not in message:
        return None  # notifications (initialized, cancelled...) need no reply
    identifier, method = message['id'], message['method']
    params = message.get('params') or {}
    if not isinstance(params, dict):
        return _error(identifier, INVALID_PARAMS, 'params must be an object')
    from .base import UnknownTool
    if method == 'initialize':
        requested = params.get('protocolVersion')
        result = {'protocolVersion': requested if requested in SUPPORTED else SUPPORTED[0],
                  'capabilities': {'tools': {'listChanged': False}},
                  'serverInfo': {'name': connector.name, 'version': connector.version}}
        if connector.instructions:
            result['instructions'] = connector.instructions
    elif method == 'ping':
        result = {}
    elif method == 'tools/list':
        result = {'tools': connector.describe()}
    elif method == 'tools/call':
        name, arguments = params.get('name'), params.get('arguments', {})
        if not isinstance(name, str):
            return _error(identifier, INVALID_PARAMS, 'tools/call needs a tool name')
        try:
            result = connector.call(name, arguments)
        except UnknownTool:
            return _error(identifier, INVALID_PARAMS, 'Unknown tool: ' + name[:64])
    else:
        return _error(identifier, METHOD_NOT_FOUND, 'Method not found: ' + method[:64])
    return {'jsonrpc': '2.0', 'id': identifier, 'result': result}


def run(connector, stdin=None, stdout=None):
    stdin = stdin or sys.stdin.buffer
    out = stdout or sys.stdout.buffer
    sys.stdout = sys.stderr  # stray print() calls in tools go to the log, never the protocol stream

    def send(row):
        out.write((json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8'))
        out.flush()

    while True:
        line = stdin.readline(MAX_LINE + 1)
        if not line:
            return
        if len(line) > MAX_LINE:
            send(_error(None, INVALID_REQUEST, 'Message too large'))
            return
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            send(_error(None, PARSE_ERROR, 'Parse error'))
            continue
        response = handle(connector, message)
        if response is not None:
            send(response)
