"""Google Drive / Docs / Sheets through the user's Google API connection (scope drive.file).

drive.file: Jarvis sees and changes only files and folders it created (or the user opened with it), so its test
folder is its own. The sign-in is the Gmail API's (gmail_api.SCOPES carries drive.file), stored DPAPI-encrypted.
Writes are approved by the caller, made once (never replayed after an uncertain result) and verified by reading
back: a Doc's text through Drive's plain-text export, a Sheet's computed cells through its CSV export.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

DRIVE = 'https://www.googleapis.com/drive/v3/'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,mimeType,parents,webViewLink'
FOLDER = 'application/vnd.google-apps.folder'
DOC = 'application/vnd.google-apps.document'
SHEET = 'application/vnd.google-apps.spreadsheet'
SCOPE = 'https://www.googleapis.com/auth/drive.file'
MAX_UPLOAD = 20 * 1024 * 1024


def available(base: Any = None) -> bool:
    """Connected Google API whose sign-in includes Drive (drive.file)."""
    from . import gmail_api
    if gmail_api.status(base) != 'connected':
        return False
    try:
        creds = gmail_api.credentials(Path(base) if base else Path(__file__).resolve().parent.parent)
    except Exception:
        return False
    return bool(getattr(creds, 'scopes', None) and SCOPE in creds.scopes)


def quoted(name: str) -> str:
    if not name or len(name) > 200 or any(c in name for c in '\r\n'):
        raise ValueError('Use a short, single-line name.')
    return name.replace('\\', '\\\\').replace("'", "\\'")


class Files:
    def __init__(self, base: Any, session: Any = None) -> None:
        if session is None:
            import requests
            from . import gmail_api
            session = requests.Session()
            session.trust_env = False
            session.headers['Authorization'] = 'Bearer ' + gmail_api.credentials(Path(base)).token
        self.session = session

    def close(self) -> None:
        self.session.close()

    def _call(self, method: str, url: str, raw: bool = False, **kwargs: Any) -> Any:
        try:
            with self.session.request(method, url, timeout=(5, 30), allow_redirects=False, **kwargs) as response:
                if not 200 <= response.status_code < 300:
                    detail = ''
                    try:
                        detail = str(response.json().get('error', {}).get('message', ''))[:200]
                    except ValueError:
                        pass
                    raise ValueError(f'Google Drive API returned HTTP {response.status_code}: {detail} '
                                     '(inspect before repeating)')
                if raw:
                    return response.content[:2_000_000]
                return response.json() if response.content.strip() else {}
        except ValueError:
            raise
        except Exception:
            raise ValueError('Google Drive API result is uncertain; inspect Drive before another write. '
                             'No automatic retry.') from None

    # Reads ---------------------------------------------------------------------------------------------------
    def find(self, name: str, mime: str = '', parent: str = '') -> List[Dict[str, Any]]:
        q = f"name = '{quoted(name)}' and trashed = false"
        if mime:
            q += f" and mimeType = '{mime}'"
        if parent:
            q += f" and '{parent}' in parents"
        data = self._call('GET', DRIVE + 'files', params={'q': q, 'fields': 'files(id,name,mimeType,parents,webViewLink)',
                                                          'pageSize': 10, 'spaces': 'drive'})
        return list(data.get('files', []))

    def text_of(self, file_id: str) -> str:
        return str(self._call('GET', DRIVE + f'files/{file_id}/export', raw=True,
                              params={'mimeType': 'text/plain'}).decode('utf-8-sig', 'replace'))

    def cells_of(self, file_id: str) -> List[List[str]]:
        text = self._call('GET', DRIVE + f'files/{file_id}/export', raw=True,
                          params={'mimeType': 'text/csv'}).decode('utf-8-sig', 'replace')
        return [row for row in csv.reader(io.StringIO(text))]

    # Writes (approved by the caller; each made once) ----------------------------------------------------------
    def folder(self, name: str) -> Dict[str, Any]:
        """The Jarvis-made folder with this name, created when missing. {id, name, created}."""
        found = self.find(name, FOLDER)
        if found:
            return {**found[0], 'created': False}
        made = self._call('POST', DRIVE + 'files', params={'fields': 'id,name,webViewLink'},
                          json={'name': name, 'mimeType': FOLDER})
        return {**made, 'created': True}

    def _upload(self, metadata: Dict[str, Any], content: bytes, content_type: str) -> Dict[str, Any]:
        boundary = 'jarvis-' + re.sub(r'\W', '', str(id(metadata)))
        body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(metadata)}\r\n'
                f'--{boundary}\r\nContent-Type: {content_type}\r\n\r\n').encode('utf-8') + content + \
            f'\r\n--{boundary}--'.encode('utf-8')
        return dict(self._call('POST', UPLOAD, data=body,
                               headers={'Content-Type': f'multipart/related; boundary={boundary}'}))

    def create_doc(self, name: str, text: str, parent: str) -> Dict[str, Any]:
        """A Google Doc made from plain text (Drive converts it on upload)."""
        return self._upload({'name': name, 'mimeType': DOC, 'parents': [parent]}, text.encode('utf-8'), 'text/plain')

    def create_sheet(self, name: str, rows: List[List[str]], parent: str) -> Dict[str, Any]:
        """A Google Sheet made from rows (CSV; formulas such as =SUM(A1:A3) are kept and computed)."""
        out = io.StringIO()
        csv.writer(out).writerows(rows)
        return self._upload({'name': name, 'mimeType': SHEET, 'parents': [parent]}, out.getvalue().encode('utf-8'),
                            'text/csv')

    def upload(self, path: Path, parent: str) -> Dict[str, Any]:
        data = path.read_bytes()
        if len(data) > MAX_UPLOAD:
            raise ValueError('The file is larger than 20 MB; upload it yourself.')
        return self._upload({'name': path.name, 'parents': [parent]}, data, 'application/octet-stream')
