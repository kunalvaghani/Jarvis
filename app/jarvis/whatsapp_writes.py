"""Conservative text-send checkpoint. No recipient or message text in journal files.

An uncertain checkpoint needs human inspection; successful sends may be repeated
only by a new explicitly approved request. This is not event-ID deduplication.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path


@contextmanager
def text_send(base, contact, text, state=None):
    root = Path(base) / '.jarvis-runtime/whatsapp/writes'
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise ValueError('WhatsApp journal cannot use a linked directory.')
    digest = hashlib.sha256(json.dumps([contact, text], ensure_ascii=False).encode('utf-8')).hexdigest()
    path, lockpath = root / (digest + '.json'), root / 'desktop.lock'
    if path.is_symlink() or lockpath.is_symlink():
        raise ValueError('WhatsApp journal cannot use linked files.')
    with lockpath.open('a+b') as lock:
        lock.seek(0, 2)
        if not lock.tell():
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError('Another WhatsApp text send is active; nothing replayed.') from None
        try:
            if path.exists():
                try:
                    with path.open(encoding='utf-8') as stream:
                        payload = stream.read(1025)
                    row = json.loads(payload)
                    if (len(payload) > 1024 or not isinstance(row, dict) or set(row) != {'pending'}
                            or type(row.get('pending')) is not bool):
                        raise ValueError()
                except (OSError, ValueError, RecursionError):
                    raise ValueError('WhatsApp journal is damaged; inspect fresh state. No replay.') from None
                if row['pending']:
                    raise ValueError('An identical WhatsApp send is uncertain; inspect the chat. No replay.')

            def save(pending):
                tmp = path.with_suffix('.tmp')
                if tmp.is_symlink():
                    raise ValueError('WhatsApp journal cannot use a linked temporary file.')
                tmp.write_text(json.dumps({'pending': pending}), encoding='utf-8')
                tmp.replace(path)

            save(True)
            if state is not None:
                state.checkpoint('uncertain_external_write', action='whatsapp_send', target=digest,
                                 evidence='Text send intent persisted; delivery not verified')
            yield
            save(False)
            if state is not None:
                state.checkpoint('external_write_verified', action='whatsapp_send', target=digest,
                                 evidence='Fresh UI outgoing status observed')
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)
