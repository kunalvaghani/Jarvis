"""Coalesce replaceable UI snapshots; preserve control events and stream barriers."""
from collections import OrderedDict, deque
import queue
import threading


class UIEventBuffer:
    def __init__(self):
        self.lock = threading.Lock()
        self.ordered = deque()
        self.pending = OrderedDict()
        self.coalesced = 0

    @staticmethod
    def key(kind, value):
        if kind in {'level', 'partial'}:
            return kind
        if kind == 'answer_stream' and isinstance(value, dict) and value.get('active', True):
            return kind, value.get('phase'), value.get('task_id')
        if kind == 'task_status' and isinstance(value, dict) and value.get('active'):
            return kind, value.get('task_id'), value.get('target'), value.get('phase')
        return None  # Approval, media, final/error/stop and DAG transitions stay ordered.

    def _flush(self):
        self.ordered.extend(self.pending.values())
        self.pending.clear()

    def put(self, row):
        kind, value = row
        key = self.key(kind, value)
        with self.lock:
            if key is None:
                self._flush()
                self.ordered.append(row)
                return
            previous = self.pending.get(key)
            if kind == 'task_status' and previous:
                value = {**previous[1], **value}
                row = kind, value
            # A new phase, generation, draft replacement or text reset is a barrier.
            if kind == 'answer_stream':
                other = any(item[0] == kind and pending_key != key for pending_key,item in self.pending.items())
                replacement = previous and 'text' in value and 'text' in previous[1] and not str(value['text'] or '').startswith(str(previous[1]['text'] or ''))
                if other or replacement:
                    self._flush()
                    previous = None
                elif previous:
                    value = {**previous[1], **value}  # A phase-only update must not lose accumulated text.
                    row = kind, value
            if previous:
                self.coalesced += 1
            self.pending[key] = row
            if len(self.pending) >= 64:
                self._flush()

    def get_nowait(self):
        with self.lock:
            if not self.ordered:
                self._flush()
            if not self.ordered:
                raise queue.Empty
            return self.ordered.popleft()

    def qsize(self):
        with self.lock:
            return len(self.ordered) + len(self.pending)

    def empty(self):
        return self.qsize() == 0
