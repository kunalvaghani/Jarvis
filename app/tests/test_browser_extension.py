"""Jarvis Browser extension: native host bridge + ExtensionRunner, with a fake extension on the Chrome side."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading

from jarvis.control.web.extension_runner import NOT_CONNECTED, ExtensionRunner

APP = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load(APP / 'browser_extension' / 'host' / 'jarvis_browser_host.py', 'jarvis_browser_host')
installer = load(APP / 'scripts' / 'install_browser_extension.py', 'install_browser_extension')


def start_bridge(folder: str, answer):
    """A bridge whose Chrome side is a fake extension calling answer(args) -> reply dict."""
    to_host_r, to_host_w = os.pipe()      # extension -> host (host's stdin)
    from_host_r, from_host_w = os.pipe()  # host -> extension (host's stdout)
    host.STATE = Path(folder) / 'browser-extension.json'
    bridge = host.Bridge(os.fdopen(to_host_r, 'rb'), os.fdopen(from_host_w, 'wb'))
    server = bridge.listen()
    seen = []

    def extension():
        reader, writer = os.fdopen(from_host_r, 'rb'), os.fdopen(to_host_w, 'wb')
        while True:
            head = reader.read(4)
            if len(head) < 4:
                return
            message = json.loads(reader.read(struct.unpack('<I', head)[0]))
            seen.append(message['args'])
            reply = json.dumps({'id': message['id'], **answer(message['args'])}).encode()
            writer.write(struct.pack('<I', len(reply)) + reply)
            writer.flush()

    def accept():
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=bridge.serve, args=(conn,), daemon=True).start()
    for target in (extension, accept, bridge.from_chrome):
        threading.Thread(target=target, daemon=True).start()
    return host.STATE, seen, server


def test_jarvis_reaches_the_extension_through_the_host():
    with tempfile.TemporaryDirectory() as folder:
        state, seen, server = start_bridge(folder, lambda args: {
            'success': True, 'data': {'tabs': [{'tabId': 't7', 'title': 'Example', 'url': 'https://example.com/'}]}})
        runner = ExtensionRunner(state=state)
        reply = runner(['tab', 'list'], timeout_s=5)
        assert reply.success and reply.data['tabs'][0]['tabId'] == 't7'
        assert seen == [['tab', 'list']]
        server.close()


def test_a_wrong_token_is_refused():
    with tempfile.TemporaryDirectory() as folder:
        state, seen, server = start_bridge(folder, lambda args: {'success': True, 'data': {}})
        port = json.loads(state.read_text())['port']
        with socket.create_connection(('127.0.0.1', port), timeout=5) as sock:
            sock.sendall(b'{"token": "guess"}\n')
            assert b'bad token' in sock.makefile('rb').readline()
        assert seen == []
        server.close()


def test_unknown_commands_never_leave_jarvis():
    runner = ExtensionRunner(state=Path(tempfile.gettempdir()) / 'no-such-state.json')
    reply = runner(['evaluate', 'document.cookie'])
    assert not reply.success and 'unknown command' in reply.error


def test_not_connected_says_so_and_counts_as_not_done():
    from jarvis.control.web.agent_browser_backend import to_error
    runner = ExtensionRunner(state=Path(tempfile.gettempdir()) / 'no-such-state.json')
    reply = runner(['open', 'https://example.com'])
    assert not reply.success and reply.error == NOT_CONNECTED
    assert to_error(reply, acting=True).executed is False  # nothing was sent: safe to report, no "may have acted"


def test_extension_id_has_chromes_form():
    ident = installer.extension_id(b'any public key bytes')
    assert len(ident) == 32 and set(ident) <= set('abcdefghijklmnop')
