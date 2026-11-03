"""Jarvis Browser extension as a runner for AgentBrowserExecutor (control.personal_chrome_link = "extension").

The extension (browser_extension/jarvis) works in the user's signed-in Chrome, only inside its own "Jarvis" tab
group, and answers the agent-browser command subset Jarvis uses with the same JSON shapes. This runner reaches it
through the native messaging host's local socket (token from .jarvis-runtime/browser-extension.json), so the
executor's logic, refs, policy and verification apply unchanged. No remote-debugging prompt: Chrome trusts the
installed extension; its "is debugging this browser" bar shows while Jarvis acts.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
import socket
import threading
import time
from typing import Any, Dict, List, Optional, Sequence

from .agent_browser_backend import Reply

APP = Path(__file__).resolve().parents[3]
STATE = APP / '.jarvis-runtime' / 'browser-extension.json'
HOST = APP / 'browser_extension' / 'host' / 'jarvis_browser_host.py'
NOT_CONNECTED = ('The Jarvis Browser extension is not connected: open Chrome (Person 1) with the Jarvis Browser '
                 'extension installed (scripts/install_browser_extension.py). Nothing was done.')
# The extension implements a fixed command set; anything else never leaves Jarvis (mirrors the agent-browser policy).
COMMANDS = frozenset({'ping', 'reload', 'render', 'close', 'tab', 'open', 'back', 'forward', 'reload', 'get', 'is', 'snapshot', 'read',
                      'click', 'dblclick', 'hover', 'rightclick', 'fill', 'select', 'check', 'uncheck', 'keyboard',
                      'press', 'scroll', 'scrollintoview', 'wait'})


class ExtensionRunner:
    auto_connect = True   # the user's own Chrome: Jarvis keeps to its own tabs (the extension enforces its group)
    profile = 'extension'
    headed = True

    def __init__(self, state: Path = STATE, session: str = 'jarvis-extension') -> None:
        self.state, self.session = state, session
        self.binary = HOST
        self.calls: List[Dict[str, Any]] = []
        self._sock: Optional[socket.socket] = None
        self._reader: Any = None
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def available(self) -> bool:
        try:
            return bool(self(['ping'], timeout_s=5).success)
        except OSError:
            return False

    def _connect(self, timeout_s: float) -> None:
        info = json.loads(self.state.read_text(encoding='utf-8'))
        sock = socket.create_connection(('127.0.0.1', int(info['port'])), timeout=min(timeout_s, 5))
        reader = sock.makefile('rb')
        sock.sendall((json.dumps({'token': info['token']}) + '\n').encode('utf-8'))
        hello = json.loads(reader.readline(4096) or b'{}')
        if not hello.get('success'):
            sock.close()
            raise OSError('the extension host refused the connection')
        self._sock, self._reader = sock, reader

    def _drop(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = self._reader = None

    def __call__(self, args: Sequence[str], timeout_s: float = 60.0) -> Reply:
        args = [str(a) for a in args]
        if not args or args[0] not in COMMANDS:
            return Reply(success=False, error=f'unknown command: {args[0] if args else ""} (not available through '
                                              'the Jarvis extension)')
        started = time.perf_counter()
        with self._lock:
            reply = self._exchange(args, timeout_s)
        if len(self.calls) < 500:
            self.calls.append({'command': args[0], 'ok': reply.success,
                               'ms': round((time.perf_counter() - started) * 1000, 1)})
        return reply

    def _exchange(self, args: List[str], timeout_s: float) -> Reply:
        for attempt in (1, 2):  # one reconnect: the host restarts with Chrome (nothing was sent on a dead socket)
            try:
                if self._sock is None:
                    self._connect(timeout_s)
                assert self._sock is not None
                ident = next(self._ids)
                self._sock.settimeout(timeout_s + 5)
                self._sock.sendall((json.dumps({'id': ident, 'args': args, 'session': self.session})
                                    + '\n').encode('utf-8'))
            except (OSError, ValueError, KeyError):
                self._drop()
                if attempt == 2:
                    return Reply(success=False, error=NOT_CONNECTED)
                continue
            try:
                while True:
                    line = self._reader.readline()
                    if not line:
                        raise OSError('the extension host closed the connection')
                    message = json.loads(line)
                    if message.get('id') == ident:
                        return Reply.model_validate({k: v for k, v in message.items() if k != 'id'})
            except (OSError, ValueError):
                # Sent, then lost: the extension may have acted. Never resend; the caller re-reads.
                self._drop()
                return Reply(success=False, error='the Jarvis extension stopped answering after the command was '
                                                  'sent; it may have acted (read the page before repeating)')
        return Reply(success=False, error=NOT_CONNECTED)
