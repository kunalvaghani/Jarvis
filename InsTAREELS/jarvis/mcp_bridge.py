"""Opt-in, short-lived MCP stdio client. All server starts need approval.

Servers are executable programs, not a security boundary. Only commands from
the app's trusted local config may start, with shell=False and no auto-retry.
Supports tools on MCP 2025-11-25; no HTTP, resources, sampling or elicitation.
"""
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

from .agent_context import bounded_text, scoped

VERSION = '2025-11-25'


def configurations(base):
    path = scoped(base, '.jarvis/mcp.json')
    if not path.is_file():
        return {}
    data = json.loads(bounded_text(path, 20000))
    if not isinstance(data, dict) or set(data) != {'servers'} or not isinstance(data['servers'], dict):
        raise ValueError('MCP config needs a servers object.')
    if len(data['servers']) > 20:
        raise ValueError('At most twenty MCP servers may be configured.')
    for name, config in data['servers'].items():
        if not re.fullmatch(r'[\w.-]{1,60}', name) or not isinstance(config, dict):
            raise ValueError('Invalid MCP server entry.')
    return data['servers']


class StdioClient:
    def __init__(self, config, base, cancelled):
        command = config.get('command')
        args = config.get('args', [])
        allowed = config.get('allow_tools', [])
        if (config.get('trusted') is not True or config.get('enabled') is not True
                or not isinstance(command, str) or not Path(command).is_absolute()
                or not Path(command).is_file() or Path(command).suffix.lower() in {'.cmd', '.bat', '.ps1', '.sh'}
                or not isinstance(args, list) or len(args) > 30 or not all(isinstance(arg, str) for arg in args)
                or not isinstance(allowed, list) or not allowed or not all(isinstance(n, str) and n != '*' for n in allowed)):
            raise ValueError('MCP requires an enabled trusted absolute executable, argument list and exact tool allowlist.')
        timeout = config.get('timeout_seconds', 20)
        if type(timeout) not in {int, float} or not 1 <= timeout <= 60:
            raise ValueError('MCP timeout must be between one and sixty seconds.')
        self.timeout, self.cancelled, self.identifier = timeout, cancelled, 0
        self.responses = queue.Queue(maxsize=64)
        env_names = config.get('env_names', [])
        if not isinstance(env_names, list) or not all(isinstance(n, str) for n in env_names):
            raise ValueError('MCP env_names must name environment variables, never contain secret values.')
        env = {key: value for key, value in os.environ.items() if key.upper() in {
            'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT', 'APPDATA', 'LOCALAPPDATA'} or key in env_names}
        if cancelled():
            raise ValueError('MCP cancelled before process start.')
        self.process = subprocess.Popen([command, *args], cwd=base, env=env, shell=False,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.thread = threading.Thread(target=self._read, daemon=True, name='jarvis-mcp-reader')
        self.thread.start()

    def _read(self):
        try:
            total = 0
            while True:
                line = self.process.stdout.readline(262145)
                total += len(line)
                if not line or len(line) > 262144 or total > 1048576:
                    self.responses.put_nowait(None)
                    return
                self.responses.put_nowait(json.loads(line))
        except (ValueError, OSError, queue.Full):
            try:
                self.responses.put_nowait(None)
            except queue.Full:
                pass

    def send(self, method, params=None, identifier=None):
        row = {'jsonrpc': '2.0', 'method': method}
        if identifier is not None:
            row['id'] = identifier
        if params is not None:
            row['params'] = params
        encoded = (json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8')
        if len(encoded) > 60000:
            raise ValueError('MCP request exceeds the size limit.')
        self._write_message(encoded)

    def _write_message(self, encoded):
        # A server that never reads stdin must not block cancellation or timeout.
        finished, errors = threading.Event(), []
        def write():
            try:
                self.process.stdin.write(encoded)
                self.process.stdin.flush()
            except (OSError, ValueError) as exc:
                errors.append(exc)
            finally:
                finished.set()
        writer = threading.Thread(target=write, daemon=True, name='jarvis-mcp-writer')
        writer.start()
        deadline = time.monotonic() + self.timeout
        while not finished.wait(.05):
            if self.cancelled() or time.monotonic() > deadline:
                raise ValueError('MCP input cancelled or timed out; no retry.')
        if errors:
            raise ValueError('MCP input failed; no retry.') from errors[0]

    def request(self, method, params=None):
        if self.cancelled():
            raise ValueError('MCP cancelled before request.')
        self.identifier += 1
        identifier = self.identifier
        self.send(method, params, identifier)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.cancelled():
                raise ValueError('MCP cancelled; inspect external effects before another call.')
            try:
                row = self.responses.get(timeout=.05)
            except queue.Empty:
                continue
            if row is None or not isinstance(row, dict) or row.get('jsonrpc') != '2.0':
                raise ValueError('MCP server stopped or returned invalid/oversized output; no retry.')
            if row.get('method') and 'id' in row:
                # Refuse server-originated requests (sampling, elicitation, roots).
                response = {'jsonrpc': '2.0', 'id': row['id'], 'error': {'code': -32601, 'message': 'Client capability unavailable'}}
                self._write_message((json.dumps(response) + '\n').encode())
                continue
            if row.get('id') != identifier:
                continue
            if 'error' in row:
                raise ValueError('MCP server returned an error; no automatic retry.')
            if 'result' not in row:
                raise ValueError('MCP response has no result.')
            return row['result']
        raise ValueError('MCP request timed out; effects may be uncertain. No automatic retry.')

    def initialize(self):
        result = self.request('initialize', {'protocolVersion': VERSION, 'capabilities': {},
            'clientInfo': {'name': 'jarvis', 'version': '1'}})
        if not isinstance(result, dict) or result.get('protocolVersion') != VERSION:
            raise ValueError('MCP server did not negotiate supported protocol ' + VERSION)
        self.send('notifications/initialized')

    def tools(self):
        rows, cursor = [], None
        for _ in range(5):
            result = self.request('tools/list', {'cursor': cursor} if cursor else {})
            if not isinstance(result, dict) or not isinstance(result.get('tools'), list):
                raise ValueError('Invalid MCP tool catalog.')
            rows.extend(result['tools'])
            if len(rows) > 100:
                raise ValueError('MCP tool catalog exceeds one hundred entries.')
            cursor = result.get('nextCursor')
            if not cursor:
                return rows
        raise ValueError('MCP tool catalog exceeds pagination limit.')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout):
            if stream:
                stream.close()
        self.thread.join(timeout=1)


def execute(actions, step, cancelled):
    base = Path(actions.base).resolve(strict=True)
    configs = configurations(base)
    if step['action'] == 'mcp_status':
        return json.dumps([{'server': name, 'enabled': config.get('enabled') is True,
                           'trusted': config.get('trusted') is True} for name, config in configs.items()])
    name = step['value']
    config = configs.get(name)
    if config is None:
        raise ValueError('Configure a trusted server in .jarvis/mcp.json first.')
    arguments = json.loads(step.get('content') or '{}')
    if not isinstance(arguments, dict):
        raise ValueError('MCP content must be a JSON object.')
    if step['action'] == 'mcp_call':
        if (set(arguments) != {'name', 'arguments'} or arguments['name'] not in config.get('allow_tools', [])
                or not isinstance(arguments['arguments'], dict)):
            raise ValueError('MCP tool must be exactly allowlisted and have an argument object.')
    # Approve the executable plus exact call; server annotations cannot waive approval.
    actions._approve(step['action'], json.dumps({'server': name, 'command': config.get('command'),
        'args': config.get('args', []), 'call': arguments}, ensure_ascii=False), cancelled)
    from .task_state import TaskState
    state = getattr(actions, 'task_state', None)
    if isinstance(state, TaskState):
        state.checkpoint('action_attempted', action=step['action'], target=name,
                         evidence='Approved MCP process/call beginning; effects require fresh inspection after failure')
    client = StdioClient(config, base, cancelled)
    try:
        client.initialize()
        rows = client.tools()
        allowed = [row for row in rows if isinstance(row, dict) and row.get('name') in config.get('allow_tools', [])]
        if step['action'] == 'mcp_list_tools':
            result = allowed
        else:
            if arguments['name'] not in {row['name'] for row in allowed}:
                raise ValueError('Allowlisted tool was not advertised by the server.')
            result = client.request('tools/call', arguments)
            if not isinstance(result, dict) or result.get('isError') is True:
                raise ValueError('MCP tool reported failure; no retry.')
        text = json.dumps(result, ensure_ascii=False)
        for key in config.get('env_names', []):
            secret = os.environ.get(key, '')
            if len(secret) >= 4:
                text = text.replace(secret, '[credential redacted]')
        if cancelled():
            raise ValueError('MCP cancelled after response; inspect effects.')
        if isinstance(state, TaskState):
            state.checkpoint('observed', action=step['action'], target=name, evidence='MCP response received; content remains untrusted')
        return text[:10000] + ('\n[MCP result truncated]' if len(text) > 10000 else '')
    finally:
        client.close()
