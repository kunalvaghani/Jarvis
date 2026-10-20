"""Run LOCALLY by a human, not from an LLM tool.
PKCE + localhost-only callback + CSRF state check + OS keyring (no plaintext).
"""
from __future__ import annotations
import argparse
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit, parse_qs
from spotify_connector.auth import (PKCETokenManager,pkce_pair,redirect_uri,
                                    authorization_url,exchange)
from spotify_connector.base import ConnectorError


def login(port=8765, timeout=180):
    client_id=os.environ.get('SPOTIFY_CLIENT_ID','').strip()
    if not client_id:raise ConnectorError('Set SPOTIFY_CLIENT_ID before authorization')
    uri=redirect_uri(port)
    verifier,challenge=pkce_pair()
    state=secrets.token_urlsafe(32)
    received={'code':None,'error':None}
    done=threading.Event()
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed=urlsplit(self.path)
            if parsed.path!='/callback':
                self.send_error(404);return
            qs=parse_qs(parsed.query)
            if qs.get('state',[None])[0]!=state:
                self.send_error(403,'Invalid OAuth state');return
            received['code']=qs.get('code',[None])[0]
            received['error']=qs.get('error',[None])[0]
            done.set()
            self.send_response(200)
            self.send_header('Content-Type','text/plain; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(b'Spotify authorization received. You can close this tab.')
        def log_message(self,format,*args):
            # Never print authorization code, tokens or query string.
            return
    server=HTTPServer(('127.0.0.1',port),Callback)
    server.timeout=0.5
    url=authorization_url(client_id,uri,state,challenge)
    print('Opening Spotify authorization in your browser; approve only if you recognize the requested permissions.')
    webbrowser.open(url)
    try:
        until=time.monotonic()+timeout
        while not done.is_set() and time.monotonic()<until:
            server.handle_request()
        if received['error']:raise ConnectorError('Spotify authorization declined')
        if not received['code']:raise ConnectorError('Spotify authorization timed out')
        token=exchange({'client_id':client_id,'grant_type':'authorization_code',
                        'code':received['code'],'redirect_uri':uri,'code_verifier':verifier})
        token['jarvis_account_consent']=True
        token['expires_at']=time.time()+int(token.get('expires_in',3600))
        PKCETokenManager(client_id).store.save(token)
        print('Spotify authorization saved to OS credential vault. No token written to files.')
    finally:
        server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args()
    login(args.port,args.timeout)
