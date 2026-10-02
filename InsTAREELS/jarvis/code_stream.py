"""Decode streamed JSON source and keep guarded, visible coding drafts."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def content_prefix(text):
    """Read a partial root content string, ignoring content-like text elsewhere."""
    decoder = json.JSONDecoder()
    pos = 0
    def space(i):
        while i < len(text) and text[i].isspace():
            i += 1
        return i
    pos = space(pos)
    if pos >= len(text) or text[pos] != '{':
        return None
    pos += 1
    while True:
        pos = space(pos)
        try:
            name, pos = decoder.raw_decode(text, pos)
        except ValueError:
            return None
        if not isinstance(name, str):
            return None
        pos = space(pos)
        if pos >= len(text) or text[pos] != ':':
            return None
        pos = space(pos + 1)
        if name == 'content':
            if pos >= len(text) or text[pos] != '"':
                return None
            start, pos = pos + 1, pos + 1
            end = start
            while pos < len(text):
                char = text[pos]
                if char == '"':
                    end = pos
                    break
                if char == '\\':
                    if pos + 1 >= len(text):
                        break
                    if text[pos + 1] == 'u':
                        if pos + 6 > len(text):
                            break
                        pos += 6
                    else:
                        pos += 2
                else:
                    pos += 1
                end = pos
            try:
                value = json.loads('"' + text[start:end] + '"')
                # Hold unfinished Unicode surrogate pairs until their next chunk.
                value.encode('utf-8')
                return value
            except (ValueError, UnicodeError):
                return None
        try:
            _, pos = decoder.raw_decode(text, pos)
        except ValueError:
            return None
        pos = space(pos)
        if pos >= len(text) or text[pos] != ',':
            return None
        pos += 1


def record_path(base, path):
    identity = hashlib.sha256(str(Path(path).resolve()).casefold().encode()).hexdigest()[:24]
    from .agent_context import scoped
    return scoped(base, '.jarvis-runtime/coding-streams/' + identity + '.json')


def owned_draft(base, path, *, allow_complete=False):
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file():
            return False
        record = record_path(base, path)
        if record.stat().st_size > 4000:
            return False
        meta = json.loads(record.read_text(encoding='utf-8'))
        return (meta.get('status') in ({'streaming', 'complete'} if allow_complete else {'streaming'}) and meta.get('path') == str(path.resolve())
                and meta.get('sha256') == hashlib.sha256(path.read_bytes()).hexdigest())
    except (OSError, ValueError, TypeError):
        return False


class CodeDraft:
    def __init__(self, base, target, original, new_file, header, cancelled, report):
        self.base, self.target = Path(base), Path(target)
        self.path = self.target if new_file else self.target.with_name(self.target.name + '.jarvis-draft')
        self.new_file, self.header = new_file, header
        self.cancelled, self.report = cancelled, report
        self.started = False
        self.last_progress = 0.
        if new_file:
            self.expected = original
        elif self.path.exists():
            if not owned_draft(self.base, self.path, allow_complete=True):
                raise ValueError('An unowned or changed streaming draft already exists: ' + str(self.path))
            self.expected = self.path.read_bytes()
        else:
            self.expected = None
        from .progress import status
        status(report, 'Generating code', self.target, file=str(self.target), preview='', outcome='Awaiting generated code')

    def write(self, content):
        if self.cancelled():
            raise ValueError('Coding cancelled; partial draft preserved.')
        if not isinstance(content, str) or len(content) > 20000 or '\x00' in content:
            raise ValueError('Invalid streaming code chunk; draft preserved.')
        from .agent_context import scoped
        scoped(self.path.parent, self.path.name)
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.expected:
            raise ValueError('The coding draft changed outside Jarvis; streaming stopped without overwriting it.')
        raw = (self.header + content).encode('utf-8')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('wb', dir=self.path.parent, prefix='.jarvis-stream-', delete=False) as output:
                temporary = Path(output.name)
                output.write(raw)
                output.flush()
            if self.expected is None:
                os.link(temporary, self.path)
            else:
                if self.path.read_bytes() != self.expected:
                    raise ValueError('The coding draft changed; streaming stopped.')
                os.replace(temporary, self.path)
            self.expected = raw
            from .skill_memory import atomic
            atomic(record_path(self.base, self.path), json.dumps({'path': str(self.path.resolve()),
                'sha256': hashlib.sha256(raw).hexdigest(), 'status': 'streaming'}))
            if not self.started:
                self.report('action', 'Streaming code into ' + str(self.path) + ' (incomplete draft; wait for validation).')
                self.started = True
            import time
            now = time.monotonic()
            if now-self.last_progress >= .25:
                from .progress import status
                status(self.report, 'Writing ' + str(len(content)) + ' chars', self.target,
                       file=str(self.target), preview=content[-1600:], characters=len(content), outcome='Incomplete draft')
                self.last_progress = now
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def complete(self):
        if not self.started:
            return
        from .skill_memory import atomic
        atomic(record_path(self.base, self.path), json.dumps({'path': str(self.path.resolve()),
            'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest(), 'status': 'complete'}))
