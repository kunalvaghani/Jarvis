"""Read-only boundary around the existing google_files.Files client.

Caller supplies its existing authenticated client and permissions. This adapter
does not construct credentials, connect accounts, publish OAuth or write Drive.
Fetched text is untrusted source data; its hash covers the returned excerpt.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from ..contracts import Source


def search(files, query: str, limit: int = 10):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100:
        raise ValueError('bounded nonempty source query required')
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError('source limit must be 1..25')
    return files.search(query, limit=limit)


def read(files, file_id: str, *, limit: int = 20000, memory=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,100}', file_id or ''):
        raise ValueError('Drive file id required from the existing search tool')
    if type(limit) is not int or not 1 <= limit <= 20000:
        raise ValueError('bounded source excerpt required')
    result = files.read(file_id, limit=limit+1)
    if result.get('id') != file_id or not isinstance(result.get('text'), str) or not result['text']:
        raise ValueError('requested Drive text unavailable; no CAD/native binary import claimed')
    text = result['text'][:limit]
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    source = Source(id='drive-'+file_id+'-'+sha[:12], locator=f'https://drive.google.com/file/d/{file_id}/view',
                    sha256=sha, retrieved_at=datetime.now(timezone.utc).isoformat(),
                    justification='Hash covers returned UTF-8 excerpt only; author/license and engineering accuracy unresolved.')
    previous = memory.get(source.id) if memory is not None else None
    if previous is not None:
        source = previous
    payload = {'source': source.model_dump(mode='json'), 'text': text, 'content_is_untrusted': True,
               'possibly_truncated': len(result['text']) > limit, 'hash_scope': 'returned UTF-8 excerpt'}
    if memory is not None:
        # Journal enforces shared credential rejection before scientific indexing.
        payload['artifact_ref'] = memory.journal.put(payload, data_type='Report')
        if previous is None:
            memory.put(source)
    return payload
