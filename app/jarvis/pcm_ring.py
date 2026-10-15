"""Bounded shared-memory PCM pool for owned capture/playback threads.

Metadata and locks stay in the owning process. Never send an arbitrary shared
memory name across the public worker protocol. The worker closes/unlinks its pool.
"""
from multiprocessing import shared_memory
import threading


class PCMBuffer:
    def __init__(self, samples):
        import numpy as np
        if type(samples) is not int or not 1 <= samples <= 24000 * 120:
            raise ValueError('Invalid PCM buffer capacity')
        self.shm = shared_memory.SharedMemory(create=True, size=samples * 4)
        self.data = np.ndarray((samples,), dtype=np.float32, buffer=self.shm.buf)
        self.free = [(0, samples)]
        self.live = {}
        self.serial = 0
        self.lock = threading.Lock()

    def put(self, audio):
        import numpy as np
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
            raise ValueError('Invalid PCM samples')
        with self.lock:
            for i, (start, length) in enumerate(self.free):
                if length >= audio.size:
                    self.data[start:start + audio.size] = audio
                    self.free[i:i+1] = [(start + audio.size, length - audio.size)] if length > audio.size else []
                    self.serial += 1
                    self.live[self.serial] = (start, audio.size)
                    return self.serial
            raise BufferError('PCM buffer full')

    def read(self, token, offset=0, count=None):
        # Copy only the requested callback/capture block. No exported shm views.
        with self.lock:
            start, size = self.live[token]
            count = size - offset if count is None else count
            if not 0 <= offset <= size or not 0 <= count <= size-offset:
                raise ValueError('Invalid PCM slice')
            return self.data[start+offset:start+offset+count].copy()

    def size(self, token):
        with self.lock:
            return self.live[token][1]

    def release(self, token):
        with self.lock:
            row = self.live.pop(token, None)
            if row is None:
                return
            rows = sorted(self.free + [row])
            self.free = []
            for start, length in rows:
                if self.free and sum(self.free[-1]) == start:
                    previous, size = self.free[-1]
                    self.free[-1] = previous, size + length
                else:
                    self.free.append((start, length))

    def close(self):
        with self.lock:
            if self.data is None:
                return
            self.data = None
            self.live.clear()
            self.free.clear()
            self.shm.close()
            self.shm.unlink()


class CaptureQueue:
    """Queue-compatible capture boundary; overflow stops capture, never overwrites."""
    def __init__(self, rate=None):
        import queue
        self.items = queue.Queue(maxsize=100)
        self.pcm = None
        if rate is not None:self.configure(rate)

    def configure(self, rate):
        if self.pcm is not None:raise RuntimeError('Capture PCM already configured')
        self.pcm = PCMBuffer(min(24000*120, rate*10))

    def put_nowait(self, row):
        import queue
        if self.pcm is None:
            return self.items.put_nowait(row)
        try:
            token = self.pcm.put(row[0])
        except BufferError:
            raise queue.Full from None
        try:
            self.items.put_nowait((token, *row[1:]))
        except queue.Full:
            self.pcm.release(token)
            raise

    def get(self, *args, **kwargs):
        token, *metadata = self.items.get(*args, **kwargs)
        if not isinstance(token, int):
            return token, *metadata
        try:
            return self.pcm.read(token), *metadata
        finally:
            self.pcm.release(token)

    def get_nowait(self):
        return self.get(block=False)

    def qsize(self):
        return self.items.qsize()

    def close(self):
        import queue
        while True:
            try:
                token, *_ = self.items.get_nowait()
                if self.pcm is not None and isinstance(token,int):self.pcm.release(token)
            except queue.Empty:break
        if self.pcm is not None:self.pcm.close()
