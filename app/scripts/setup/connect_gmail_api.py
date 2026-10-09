"""Interactive local OAuth only; never part of automatic recovery."""
import hashlib
import json
from pathlib import Path
import sys
from jarvis.gmail_api import API, SCOPES, directory, save_credentials
import jarvis.gmail_api as adapter


def main():
    base=Path(__file__).resolve().parents[2]
    if sys.argv[1:]==['--verify-existing']:
        verify_existing(base)
        print('Existing encrypted Gmail connection reverified locally. No new consent or mailbox write.')
        return
    path=Path(sys.argv[1].strip('"') if len(sys.argv)>1 else input('Local Desktop OAuth client JSON path: ').strip().strip('"')).expanduser().resolve(strict=True)
    config=json.loads(path.read_text())
    installed=config.get('installed',{})
    if installed.get('auth_uri')!='https://accounts.google.com/o/oauth2/auth' or installed.get('token_uri')!='https://oauth2.googleapis.com/token':
        raise ValueError('Use a Google Desktop OAuth client JSON with official Google endpoints.')
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow=InstalledAppFlow.from_client_config(config,SCOPES,autogenerate_code_verifier=True)
    credentials=flow.run_local_server(host='127.0.0.1',port=0,open_browser=True,timeout_seconds=300,
        authorization_prompt_message='Complete the Google authorization in your browser.',
        success_message='Jarvis Gmail API is connected. You can close this tab.',access_type='offline',prompt='consent')
    if not credentials.has_scopes(SCOPES):raise ValueError('Google did not grant the required read, compose and modify scopes.')
    save_credentials(base,credentials)
    verify_existing(base)
    print('Gmail API connected locally. Read, draft, send, Trash and label tools available; nothing was sent.')


def verify_existing(base):
    """Explicit maintenance check after a reviewed adapter update, never recovery."""
    api=API(base)
    try:api.call('GET','profile')
    finally:api.close()
    root=directory(base)
    temporary=root/'verified.tmp'
    temporary.write_text(json.dumps({'adapter_hash':hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest(),'profile_verified':True}))
    temporary.replace(root/'verified.json')


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Gmail setup failed ('+type(error).__name__+'). Check local client setup; credentials are not printed.')
        sys.exit(1)
