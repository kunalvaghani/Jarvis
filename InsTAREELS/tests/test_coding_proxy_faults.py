"""Actual loopback proxy failure boundaries; the model transport is a fixture."""
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests
from jarvis import codex_proxy, claude_code_proxy


class CodingProxyFaults(unittest.TestCase):
    def check_timeout(self,module,codex):
        with tempfile.TemporaryDirectory() as folder:
            servers=[];client=MagicMock();client.__enter__.return_value=client
            client.post.side_effect=requests.Timeout('synthetic inference timeout')
            payload={'model':'jarvis-codex-qwen3.5:9b' if codex else 'jarvis-claude-qwen3.5:9b','tools':[]}
            def server(*args):
                value=ThreadingHTTPServer(*args);value.handle_error=Mock();servers.append(value);return value
            with patch.object(module,'ThreadingHTTPServer',side_effect=server), \
                 patch('jarvis.knowledge_worker.session',return_value=client), \
                 patch.object(module,'prepare',return_value=payload if codex else ('/v1/messages',payload)):
                scope=patch.object(codex_proxy,'worker_scope',return_value=payload)
                with scope:
                    thread=threading.Thread(target=module.serve,args=(folder,));thread.start()
                    connection=None
                    try:
                        deadline=time.monotonic()+3
                        while not (Path(folder)/'proxy-ready.json').exists() and time.monotonic()<deadline:time.sleep(.01)
                        self.assertTrue(servers)
                        connection=http.client.HTTPConnection('127.0.0.1',servers[0].server_port,timeout=3)
                        connection.request('POST','/v1/responses' if codex else '/v1/messages',body='{}')
                        with self.assertRaises(http.client.RemoteDisconnected):connection.getresponse()
                        self.assertEqual(client.post.call_count,1)
                        self.assertEqual(client.gpu_role,'coding')
                        servers[0].handle_error.assert_not_called()
                        if codex:self.assertIn('"stage": "failed"',(Path(folder)/'proxy-events.jsonl').read_text())
                    finally:
                        if connection:connection.close()
                        if servers:servers[0].shutdown()
                        thread.join(3)
                    self.assertFalse(thread.is_alive())

    def test_codex_timeout_closes_connection_without_replay(self):self.check_timeout(codex_proxy,True)

    def test_claude_timeout_closes_connection_without_replay(self):self.check_timeout(claude_code_proxy,False)

    def test_codex_completion_waits_for_lease_cleanup_before_client_can_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            servers=[];entered=threading.Event();release=threading.Event();finished=threading.Event();received=[]
            client=MagicMock();client.__enter__.return_value=client
            response=MagicMock();response.__enter__.return_value=response
            response.status_code=200;response.headers={'Content-Type':'text/event-stream'}
            def lines(**kwargs):
                yield b'data: {"type":"response.completed","response":{"output":[]}}'
                raise AssertionError('Terminal completion must stop upstream iteration.')
            response.iter_lines.side_effect=lines
            def close():entered.set();release.wait(3)
            response.close.side_effect=close;client.post.return_value=response
            def server(*args):
                value=ThreadingHTTPServer(*args);value.handle_error=Mock();servers.append(value);return value
            payload={'model':'jarvis-codex-qwen3.5:9b','tools':[]}
            def request():
                connection=http.client.HTTPConnection('127.0.0.1',servers[0].server_port,timeout=4)
                try:
                    connection.request('POST','/v1/responses',body='{}');received.append(connection.getresponse().read())
                finally:connection.close();finished.set()
            with patch.object(codex_proxy,'ThreadingHTTPServer',side_effect=server),patch('jarvis.knowledge_worker.session',return_value=client),patch.object(codex_proxy,'prepare',return_value=payload),patch.object(codex_proxy,'worker_scope',return_value=payload):
                thread=threading.Thread(target=codex_proxy.serve,args=(folder,));thread.start();caller=None
                try:
                    deadline=time.monotonic()+3
                    while not (Path(folder)/'proxy-ready.json').exists() and time.monotonic()<deadline:time.sleep(.01)
                    self.assertTrue(servers);caller=threading.Thread(target=request);caller.start()
                    self.assertTrue(entered.wait(2));self.assertFalse(finished.is_set())
                    release.set();caller.join(3)
                    self.assertTrue(finished.is_set());self.assertIn(b'response.completed',received[0]);self.assertTrue(received[0].endswith(b'\n\n'))
                    self.assertEqual(client.post.call_count,1);response.close.assert_called_once();servers[0].handle_error.assert_not_called()
                finally:
                    release.set()
                    if servers:servers[0].shutdown()
                    thread.join(3)
                    if caller:caller.join(3)
                self.assertFalse(thread.is_alive())


if __name__=='__main__':unittest.main()
