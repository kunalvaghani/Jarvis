"""Gmail connection state is reported with the one step that fixes it; no network, no credentials read."""
import hashlib
import json
from pathlib import Path

import pytest

from jarvis import gmail_api


def connect(base, adapter_hash):
    root = gmail_api.directory(base)
    root.mkdir(parents=True)
    (root / 'token.dpapi').write_bytes(b'encrypted')
    (root / 'verified.json').write_text(json.dumps({'adapter_hash': adapter_hash, 'profile_verified': True}))


def test_not_connected(tmp_path):
    assert gmail_api.status(tmp_path) == 'not_connected'
    assert 'not connected yet' in gmail_api.unavailable(tmp_path) and 'Connect Jarvis Gmail API.cmd' in gmail_api.unavailable(tmp_path)


def test_adapter_changed_points_to_read_only_reverification(tmp_path):
    connect(tmp_path, 'old-hash')
    assert gmail_api.status(tmp_path) == 'adapter_changed'
    assert '--verify-existing' in gmail_api.unavailable(tmp_path) and 'not available' in gmail_api.unavailable(tmp_path)


def test_connected(tmp_path):
    connect(tmp_path, hashlib.sha256(Path(gmail_api.__file__).read_bytes()).hexdigest())
    assert gmail_api.status(tmp_path) == 'connected'


def test_rejected_sign_in_says_reconnect_without_printing_credentials(tmp_path, monkeypatch):
    import win32crypt
    from google.oauth2.credentials import Credentials
    connect(tmp_path, 'x')
    monkeypatch.setattr(win32crypt, 'CryptUnprotectData', lambda *a: (None, b'{"refresh_token": "secret-token"}'))

    class Expired:
        valid = False

        def has_scopes(self, scopes):
            return True

        def refresh(self, request):
            raise RuntimeError("('invalid_grant: Token has been expired or revoked.', {'error': 'invalid_grant'})")
    monkeypatch.setattr(Credentials, 'from_authorized_user_info', classmethod(lambda cls, info, scopes: Expired()))
    with pytest.raises(ValueError) as caught:
        gmail_api.credentials(tmp_path)
    assert 'expired or revoked' in str(caught.value) and 'secret-token' not in str(caught.value)
