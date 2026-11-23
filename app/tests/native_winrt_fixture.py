"""Cold native projection startup is separate from synthetic WinRT assertions.

Only the two read-only repository fixtures below are callable. No retry, media
action, user-account query, ambient PYTHONPATH or shared-process termination.
"""
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

ALLOWED=frozenset({
    'test_island_desk.ApprovalAndMediaTests.test_media_metadata_multiple_sources_and_missing_properties_are_explicit',
    'test_island_desk.ApprovalAndMediaTests.test_media_metadata_reads_real_winrt_memory_stream_and_excludes_browser_session',
})
READY='JARVIS_NATIVE_FIXTURE_READY\n'


def run_fixture(identity):
    if identity not in ALLOWED:raise ValueError('Only reviewed read-only WinRT fixtures are callable')
    from jarvis.harness_process import OwnedJob,hidden_spawn
    environment={k:v for k,v in os.environ.items() if k.upper() in {
        'SYSTEMROOT','WINDIR','TEMP','TMP','PATH','PATHEXT','COMSPEC','USERPROFILE','LOCALAPPDATA','APPDATA'}}
    environment.update(JARVIS_STREAM_TEST_CHILD='1',PYTHONUTF8='1')
    argv=[sys.executable,'-I','-B',str(Path(__file__).resolve()),identity]
    job=OwnedJob();process=None
    try:
        started=time.monotonic()
        process=hidden_spawn(job,subprocess.Popen)(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,encoding='utf-8',env=environment)
        messages=queue.Queue(maxsize=1)
        def ready():
            try:messages.put(process.stdout.readline(129))
            except (OSError,ValueError):messages.put('')
        reader=threading.Thread(target=ready,daemon=True);reader.start()
        try:line=messages.get(timeout=30)
        except queue.Empty:raise subprocess.TimeoutExpired(argv,30) from None
        if line!=READY:
            raise RuntimeError('Native fixture did not complete bounded projection startup')
        startup=time.monotonic()-started
        # The original 15-second assertion/clean-exit budget remains unchanged.
        stdout,stderr=process.communicate('RUN\n',timeout=15)
        if len(stdout)+len(stderr)>256000:raise ValueError('Native fixture output exceeded its bound')
        result=subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)
        result.startup_seconds=startup
        return result
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.communicate(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                job.close()
                try:process.wait(timeout=2)
                except (OSError,subprocess.TimeoutExpired):pass
        job.close()


def worker(identity):
    if identity not in ALLOWED or os.environ.get('JARVIS_STREAM_TEST_CHILD')!='1':
        raise ValueError('Unknown or unscoped native fixture')
    # -I excludes ambient Python paths. Add only the owned application/tests.
    here=Path(__file__).resolve().parent
    sys.path[:0]=[str(here),str(here.parent)]
    import unittest
    import winrt.windows.media.control
    import winrt.windows.storage.streams
    suite=unittest.defaultTestLoader.loadTestsFromName(identity)
    print(READY,end='',flush=True)
    if sys.stdin.readline()!='RUN\n':raise ValueError('Fixture execution was not admitted')
    result=unittest.TextTestRunner().run(suite)
    import gc
    gc.collect()  # Release fixture objects while their native projections are alive.
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('one reviewed fixture identity required')
    raise SystemExit(worker(sys.argv[1]))
