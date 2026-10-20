"""One opt-in Spotify MCP child per Actions owner; repair never replays a tool."""
from contextlib import contextmanager
import json
import threading
import time

_OWNER_LOCK = threading.Lock()


class PersistentMCP:
    def __init__(self, base, stopped=lambda: False, clock=time.monotonic):
        self.base, self.stopped, self.clock = base, stopped, clock
        self.lock = threading.RLock()
        self.client = None
        self.rows = None
        self.config = None
        self.fingerprint = None
        self.next_start = 0
        self.failures = 0
        self.closed = False

    def _drop(self, failed=False):
        client, self.client, self.rows = self.client, None, None
        if client is not None:
            client.close()
        if failed:
            self.failures += 1
            self.next_start = self.clock() + min(60, 2 ** min(self.failures, 6))
            from .recovery import record
            record(self.base, 'Spotify MCP stopped; no command replayed; bounded restart backoff.')

    def _start(self, config, cancelled):
        from .mcp_bridge import StdioClient
        if self.closed or self.stopped() or cancelled():
            raise ValueError('Spotify MCP stopped or cancelled; no start.')
        if self.clock() < self.next_start:
            raise ValueError('Spotify MCP restart backoff; inspect the last action before repeating.')
        self.config = dict(config)
        client = StdioClient(config, self.base, cancelled)
        try:
            client.initialize()
            rows = client.tools()
        except BaseException:
            client.close()
            self._drop(failed=True)
            raise
        self.client, self.rows = client, rows
        self.fingerprint = json.dumps(config, sort_keys=True)
        self.failures, self.next_start = 0, 0
        from .recovery import record
        record(self.base, 'Spotify MCP initialized; no previous command replayed.')

    @contextmanager
    def session(self, config, cancelled):
        while not self.lock.acquire(timeout=.05):
            if cancelled() or self.closed or self.stopped():
                raise ValueError('Spotify MCP admission cancelled; nothing dispatched.')
        try:
            if self.closed or self.stopped() or cancelled():
                raise ValueError('Spotify MCP admission cancelled; nothing dispatched.')
            if self.client is not None and (self.client.process.poll() is not None
                    or self.fingerprint != json.dumps(config, sort_keys=True)):
                self._drop(failed=self.client.process.poll() is not None)
            if self.client is None:
                self._start(config, cancelled)
            self.client.cancelled = lambda: cancelled() or self.closed or self.stopped()
            try:
                yield self.client, self.rows
            except BaseException:
                self._drop(failed=True)
                raise
            finally:
                if self.client is not None:
                    self.client.cancelled = lambda: self.closed or self.stopped()
        finally:
            self.lock.release()

    def healthy(self):
        if self.closed or self.stopped() or self.config is None:
            return True
        if not self.lock.acquire(blocking=False):
            return True  # An in-flight call owns its bounded I/O deadline.
        try:
            if self.client is None or self.client.process.poll() is not None:
                return False
            timeout = self.client.timeout
            self.client.timeout = 2
            try:
                return self.client.request('ping') == {}
            except Exception:
                self._drop(failed=True)
                return False
            finally:
                if self.client is not None:
                    self.client.timeout = timeout
        finally:
            self.lock.release()

    def repair(self):
        if self.closed or self.stopped() or self.config is None:
            return False
        if not self.lock.acquire(blocking=False):
            return None
        try:
            if self.client is not None and self.client.process.poll() is None:
                return True
            if self.clock() < self.next_start:
                return None
            self._drop()
            self._start(self.config, lambda: self.closed or self.stopped())
            return True
        except Exception:
            return False
        finally:
            self.lock.release()

    def close(self):
        self.closed = True  # Also fences an in-flight request before waiting for its lock.
        if self.lock.acquire(timeout=3):
            try:
                self._drop()
            finally:
                self.lock.release()
        else:
            # Bounded shutdown can reap this owned child while a cancelled caller unwinds.
            client, self.client, self.rows = self.client, None, None
            if client is not None:
                client.close()


def owner(actions):
    with _OWNER_LOCK:
        current = getattr(actions, '_spotify_mcp', None)
        if current is None:
            stopped = lambda: bool(getattr(getattr(actions, 'closed', None), 'is_set', lambda: False)())
            current = actions._spotify_mcp = PersistentMCP(actions.base, stopped)
        return current
