"""Prepare a local unpacked Chrome extension. Does not install or touch profiles."""
import json
from pathlib import Path
import secrets
import shutil
import hashlib


def main():
    base=Path(__file__).resolve().parents[2]
    source=base/'integrations/gmail-chrome';target=base/'.jarvis-runtime/gmail-extension'
    target.mkdir(parents=True,exist_ok=True)
    config=target/'connection.json'
    token=json.loads(config.read_text())['token'] if config.exists() else secrets.token_hex(32)
    names=('manifest.json','background.js','gmail-content.js','keepalive.js')
    source_hash=hashlib.sha256(b''.join((source/name).read_bytes() for name in names)).hexdigest()
    for name in names:
        shutil.copy2(source/name,target/name)
    config.write_text(json.dumps({'token':token,'source_hash':source_hash})+'\n')
    (target/'local-config.js').write_text('const JARVIS_LOCAL_TOKEN = '+json.dumps(token)+';\nconst JARVIS_SOURCE_HASH = '+json.dumps(source_hash)+';\n')
    print('Local adapter prepared. In Chrome open chrome://extensions, enable Developer mode, click Load unpacked, and choose:')
    print(target)
    print('Reload the existing Gmail tab. No credentials or cookies are copied. Sending is disabled in this adapter.')


if __name__=='__main__':main()
