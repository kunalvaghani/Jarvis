"""Native messaging host for the Jarvis Browser extension (com.jarvis.browser): Chrome <-> Jarvis.

Chrome starts this process for the Jarvis extension only (allowed_origins in the host manifest) and talks to it over
stdin/stdout (4-byte length + JSON). Jarvis reaches it over a local TCP socket on 127.0.0.1 with a random token
written to ``.jarvis-runtime/browser-extension.json`` (user-only file). Lines on the socket are JSON:
``{"token": ...}`` once, then ``{"id": n, "args": [...]}`` -> ``{"id": n, "success": ..., "data"|"error": ...}``.
Nothing here interprets page content; it only relays.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import struct
import sys
import threading
from typing import Any, Dict, Optional, Tuple

APP = Path(__file__).resolve().parents[2]
STATE = APP / '.jarvis-runtime' / 'browser-extension.json'
MAX_LINE = 64 * 1024 * 1024


class Bridge:
    def __init__(self, stdin: Any, stdout: Any) -> None:
        self.stdin, self.stdout = stdin, stdout
        self.write_lock = threading.Lock()
        self.pending: Dict[str, Tuple[socket.socket, Any]] = {}
        self.pending_lock = threading.Lock()
        self.counter = 0
        self.token = secrets.token_urlsafe(32)

    # Chrome side ---------------------------------------------------------------------------------------------
    def read_native(self) -> Optional[Dict[str, Any]]:
        head = self.stdin.read(4)
        if len(head) < 4:
            return None
        size = struct.unpack('<I', head)[0]
        body = self.stdin.read(size)
        message = json.loads(body.decode('utf-8'))
        return message if isinstance(message, dict) else {}

    def write_native(self, message: Dict[str, Any]) -> None:
        data = json.dumps(message).encode('utf-8')
        with self.write_lock:
            self.stdout.write(struct.pack('<I', len(data)) + data)
            self.stdout.flush()

    def from_chrome(self) -> None:
        """Replies from the extension go back to the Jarvis connection that asked."""
        while True:
            message = self.read_native()
            if message is None:
                return  # Chrome closed the port: the extension or the browser went away
            with self.pending_lock:
                target = self.pending.pop(str(message.get('id')), None)
            if target is None:
                continue
            conn, client_id = target
            message['id'] = client_id
            try:
                conn.sendall((json.dumps(message) + '\n').encode('utf-8'))
            except OSError:
                pass

    # Jarvis side ---------------------------------------------------------------------------------------------
    def serve(self, conn: socket.socket) -> None:
        reader = conn.makefile('rb')
        try:
            first = json.loads(reader.readline(4096) or b'{}')
            if not secrets.compare_digest(str(first.get('token', '')), self.token):
                conn.sendall(b'{"success": false, "error": "bad token"}\n')
                return
            conn.sendall(b'{"success": true, "data": {"hello": "jarvis-browser"}}\n')
            while True:
                line = reader.readline(MAX_LINE)
                if not line:
                    return
                request = json.loads(line)
                with self.pending_lock:
                    self.counter += 1
                    key = str(self.counter)
                    self.pending[key] = (conn, request.get('id'))
                self.write_native({'id': key, 'args': [str(a) for a in request.get('args', [])]})
        except (OSError, ValueError):
            return
        finally:
            conn.close()

    def listen(self) -> socket.socket:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('127.0.0.1', 0))
        server.listen(4)
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({'port': server.getsockname()[1], 'token': self.token, 'pid': os.getpid()}),
                         encoding='utf-8')
        return server


def main() -> int:
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    bridge = Bridge(sys.stdin.buffer, sys.stdout.buffer)
    server = bridge.listen()

    def accept() -> None:
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=bridge.serve, args=(conn,), daemon=True).start()
    threading.Thread(target=accept, daemon=True).start()
    try:
        bridge.from_chrome()
    finally:
        server.close()
        try:
            if json.loads(STATE.read_text(encoding='utf-8')).get('pid') == os.getpid():
                STATE.unlink()
        except (OSError, ValueError):
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
