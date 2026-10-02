"""Bounded one-shot Spotify observations/transport, isolated from desktop tasks."""
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from PIL import Image

TRANSPORT = {'play','pause','next','previous','shuffle_on','shuffle_off','repeat_off','repeat_one','repeat_all'}


async def metadata():
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    from .spotify import _spotify_session
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    session = _spotify_session(manager)
    properties = await session.try_get_media_properties_async()
    if properties is None:
        raise ValueError('Spotify has not exposed its track metadata yet.')
    timeline = session.get_timeline_properties()
    result = {'title': properties.title[:300], 'artist': properties.artist[:300],
              'album': properties.album_title[:300], 'status': session.get_playback_info().playback_status.name.lower(),
              'position': max(0, timeline.position.total_seconds()), 'duration': max(0, timeline.end_time.total_seconds()),
              'source': session.source_app_user_model_id[:300], 'image': ''}
    if properties.thumbnail:
        stream = reader = None
        try:
            from winrt.windows.storage.streams import DataReader
            stream = await properties.thumbnail.open_read_async()
            if 0 < stream.size <= 2_000_000:
                reader = DataReader(stream.get_input_stream_at(0))
                count = await reader.load_async(int(stream.size))
                raw = bytearray(count)
                reader.read_bytes(raw)
                result['image'] = thumbnail(raw)
        except (OSError, ValueError, RuntimeError, ImportError):
            pass  # Track information is still useful without artwork.
        finally:
            if reader:
                reader.close()
            if stream:
                stream.close()
    return result


def thumbnail(raw):
    if not raw or len(raw)>2_000_000:
        return ''
    with Image.open(io.BytesIO(raw)) as image:
        if image.width*image.height > 4_000_000:
            return ''
        image.thumbnail((192,192))
        output = io.BytesIO()
        image.convert('RGB').save(output,format='PNG')
        return base64.b64encode(output.getvalue()).decode('ascii')


class MediaJobs:
    """Only owned child processes; no automatic mutation retry or app launch."""
    def __init__(self, report, base):
        self.report, self.base = report, Path(base)
        self.lock = threading.Lock()
        self.process = None
        self.busy = self.closed = False
        self.started = 0.

    def start(self, action='observe'):
        if action != 'observe' and action not in TRANSPORT:
            raise ValueError('Unsupported island transport')
        with self.lock:
            if self.closed or self.busy:
                return False
            self.busy, self.started = True, time.monotonic()
        threading.Thread(target=self._run,args=(action,),daemon=True,name='island-media-once').start()
        return True

    def _run(self, action):
        process = None
        try:
            with self.lock:
                if self.closed:
                    return
                process = self.process = subprocess.Popen([sys.executable,'-m','jarvis.island_media',action],
                    cwd=self.base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    encoding='utf-8', creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            output,_ = process.communicate(timeout=8)
            if process.returncode or len(output)>400_000:
                raise ValueError('Spotify observation failed.' if action=='observe' else 'Spotify request ended without a verified result; inspect playback before repeating.')
            result = json.loads(output)
            if not self.closed:
                self.report('island_media',result)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            if process and process.poll() is None:
                process.kill()
                process.communicate(timeout=2)
            if not self.closed:
                self.report('island_media',{'error': str(exc) if action=='observe' else
                    'Spotify request could not be verified. Check playback before repeating; no retry was sent.'})
        finally:
            with self.lock:
                self.process, self.busy = None, False

    def healthy(self):
        return not self.closed and (not self.busy or time.monotonic()-self.started < 12)

    def repair(self):
        # Cancel a stuck observation; mutations are never restarted by recovery.
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.kill()

    def close(self):
        with self.lock:
            self.closed = True
            if self.process and self.process.poll() is None:
                self.process.kill()


def main():
    action = sys.argv[1] if len(sys.argv)>1 else 'observe'
    try:
        if action=='observe':
            result = asyncio.run(asyncio.wait_for(metadata(),6))
        elif action in TRANSPORT:
            from .spotify import _control
            message = asyncio.run(asyncio.wait_for(_control(action,lambda:False),6))
            result = {'transport_message': message}
        else:
            raise ValueError('Unsupported island transport')
    except Exception as exc:
        result = {'error': str(exc)[:400] if action=='observe' else
                  'Spotify request could not be verified. Inspect playback before repeating; no retry was sent.'}
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()
