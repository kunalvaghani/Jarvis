"""Real stdio subprocess speaking raw JSON-RPC to the built-in runtime (no SDK, no mocks)."""
import json
import subprocess
import sys

from conftest import ROOT

NOTES = ROOT / 'connectors' / 'notes' / 'server.py'


def session(messages, *args):
    """Send newline-delimited messages, close stdin, return (decoded stdout rows, stderr)."""
    payload = ''.join((m if isinstance(m, str) else json.dumps(m)) + '\n' for m in messages)
    done = subprocess.run([sys.executable, str(NOTES), '--runtime', 'builtin', *args], input=payload.encode(),
                          capture_output=True, timeout=30)
    rows = [json.loads(line) for line in done.stdout.decode().splitlines()]
    return rows, done.stderr.decode()


def request(identifier, method, params=None):
    row = {'jsonrpc': '2.0', 'id': identifier, 'method': method}
    if params is not None:
        row['params'] = params
    return row


INIT = request(1, 'initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                 'clientInfo': {'name': 'test', 'version': '1'}})
INITIALIZED = {'jsonrpc': '2.0', 'method': 'notifications/initialized'}


def test_handshake_listing_and_calls_over_real_stdio():
    rows, _ = session([INIT, INITIALIZED, request(2, 'tools/list', {}),
                       request(3, 'tools/call', {'name': 'search_notes', 'arguments': {'query': 'local connector'}}),
                       request(4, 'tools/call', {'name': 'read_note', 'arguments': {'filename': '../secret.md'}}),
                       request(5, 'ping')])
    by_id = {row['id']: row for row in rows}
    assert len(rows) == 5  # the notification got no reply
    assert by_id[1]['result']['protocolVersion'] == '2025-11-25'
    assert by_id[1]['result']['serverInfo']['name'] == 'jarvis-notes'
    assert {t['name'] for t in by_id[2]['result']['tools']} == {'list_notes', 'read_note', 'search_notes'}
    found = by_id[3]['result']
    assert found['isError'] is False and found['structuredContent']['result'][0]['filename'] == 'welcome.md'
    assert by_id[4]['result']['isError'] is True
    assert by_id[5]['result'] == {}


def test_protocol_errors_are_json_rpc_errors():
    rows, _ = session([INIT, '{not json', request(2, 'resources/list'),
                       request(3, 'tools/call', {'name': 'no_such_tool', 'arguments': {}}),
                       request(4, 'tools/call', {'arguments': {}})])
    codes = [row.get('error', {}).get('code') for row in rows[1:]]
    assert codes == [-32700, -32601, -32602, -32602]


def test_older_protocol_is_echoed_and_unknown_one_gets_latest():
    assert session([request(1, 'initialize', {'protocolVersion': '2025-06-18'})])[0][0]['result']['protocolVersion'] == '2025-06-18'
    assert session([request(1, 'initialize', {'protocolVersion': '1999-01-01'})])[0][0]['result']['protocolVersion'] == '2025-11-25'


def test_tool_print_cannot_corrupt_the_protocol_stream(tmp_path):
    from jarvis_connector import BaseConnector, stdio_runtime, tool
    import io

    class Noisy(BaseConnector):
        name = 'noisy'

        @tool()
        def talk(self) -> str:
            """Print, then return."""
            print('this must go to stderr')
            return 'ok'

    out = io.BytesIO()
    stdin = io.BytesIO((json.dumps(request(1, 'tools/call', {'name': 'talk', 'arguments': {}})) + '\n').encode())
    saved = sys.stdout
    try:
        stdio_runtime.run(Noisy(), stdin=stdin, stdout=out)
    finally:
        sys.stdout = saved
    rows = [json.loads(line) for line in out.getvalue().decode().splitlines()]
    assert len(rows) == 1 and rows[0]['result']['structuredContent'] == {'result': 'ok'}
