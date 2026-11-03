"""Install the Jarvis Browser extension's native messaging host (once, per user, no admin rights).

    python scripts/install_browser_extension.py

1. A signing key in secrets/ (created once) gives the unpacked extension a fixed ID: its public half goes into
   browser_extension/jarvis/manifest.json ("key").
2. The host manifest (.jarvis-runtime/native-host/com.jarvis.browser.json) lets only that extension ID start
   browser_extension/host/jarvis_browser_host.py.
3. HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\com.jarvis.browser points Chrome at the host manifest.

Then, once, in Chrome (Person 1): chrome://extensions -> Developer mode on -> Load unpacked ->
browser_extension/jarvis. Chrome does not let programs install extensions silently.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
EXTENSION = APP / 'browser_extension' / 'jarvis'
HOST_SCRIPT = APP / 'browser_extension' / 'host' / 'jarvis_browser_host.py'
KEY = APP / 'secrets' / 'jarvis-browser-extension.pem'
NATIVE = APP / '.jarvis-runtime' / 'native-host'
NAME = 'com.jarvis.browser'
REGISTRY = 'Software\\Google\\Chrome\\NativeMessagingHosts\\' + NAME


def public_der() -> bytes:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    if not KEY.exists():
        KEY.parent.mkdir(parents=True, exist_ok=True)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        KEY.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    loaded = serialization.load_pem_private_key(KEY.read_bytes(), password=None)
    return loaded.public_key().public_bytes(serialization.Encoding.DER,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)


def extension_id(der: bytes) -> str:
    """Chrome's ID for an extension with this key: the first 16 bytes of SHA-256, hex digits mapped 0-f -> a-p."""
    return ''.join(chr(ord('a') + int(c, 16)) for c in hashlib.sha256(der).hexdigest()[:32])


def main() -> int:
    der = public_der()
    ident = extension_id(der)
    manifest_path = EXTENSION / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['key'] = base64.b64encode(der).decode('ascii')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

    NATIVE.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable)
    launcher = NATIVE / 'jarvis_browser_host.bat'
    # -I: isolated mode (no user site, no current-directory imports). @echo off: stdout is the message channel.
    launcher.write_text(f'@echo off\r\n"{python}" -I "{HOST_SCRIPT}" %*\r\n', encoding='ascii')
    host_manifest = NATIVE / f'{NAME}.json'
    host_manifest.write_text(json.dumps({
        'name': NAME, 'description': 'Jarvis Browser bridge', 'path': str(launcher), 'type': 'stdio',
        'allowed_origins': [f'chrome-extension://{ident}/']}, indent=2), encoding='utf-8')
    if sys.platform == 'win32':
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(host_manifest))
    print(f'Extension ID: {ident}')
    print(f'Host manifest: {host_manifest}')
    print('Now, once, in Chrome (Person 1): chrome://extensions -> Developer mode -> Load unpacked -> '
          f'{EXTENSION}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
