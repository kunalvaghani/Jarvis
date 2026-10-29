"""D1: local browser test site. Static pages plus /slow, /redirect and /data endpoints.

Binds 127.0.0.1 only on an ephemeral port. Two instances give two origins for cross-origin iframes.
"""
from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent / 'pages'


class Handler(SimpleHTTPRequestHandler):
    peer = ''  # Base URL of the other origin, for cross-origin pages.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        if url.path == '/slow':
            time.sleep(min(10.0, float(query.get('ms', ['1000'])[0]) / 1000))
            return self.send_text('<title>Slow</title><p id="done">slow page loaded</p>', 'text/html')
        if url.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', query.get('to', ['/'])[0])
            self.end_headers()
            return None
        if url.path == '/data':
            time.sleep(min(5.0, float(query.get('ms', ['0'])[0]) / 1000))
            return self.send_text(json.dumps({'items': ['alpha', 'beta', 'gamma']}), 'application/json')
        if url.path == '/peer':
            return self.send_text(json.dumps({'peer': self.peer}), 'application/json')
        return super().do_GET()

    def send_text(self, body: str, kind: str) -> None:
        data = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Site:
    """Two origins on 127.0.0.1 (different ports = different origins and sites for isolation)."""

    def __init__(self) -> None:
        self.servers: list[ThreadingHTTPServer] = []

    def start(self) -> Tuple[str, str]:
        bases = []
        for _ in range(2):
            handler = type('BoundHandler', (Handler,), {})
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.servers.append(server)
            bases.append(f'http://127.0.0.1:{server.server_address[1]}')
        self.servers[0].RequestHandlerClass.peer = bases[1]
        self.servers[1].RequestHandlerClass.peer = bases[0]
        return bases[0], bases[1]

    @property
    def ports(self) -> Tuple[int, ...]:
        return tuple(server.server_address[1] for server in self.servers)

    def stop(self) -> None:
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.servers.clear()


def main(port: Optional[int] = None) -> None:
    site = Site()
    print(*site.start())
    try:
        while True:
            time.sleep(3600)
    finally:
        site.stop()


if __name__ == '__main__':
    main()
