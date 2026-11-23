"""No desktop input: cover mixed physical/injected transport and tuple compatibility."""
import io
import queue
from types import SimpleNamespace
from jarvis.demonstration import MouseHook,HookEvent,classify_input


def test_child_protocol_preserves_already_running_legacy_parents(monkeypatch,capsys):
    from jarvis import demonstration
    def fake_process(emit):
        return SimpleNamespace(run=lambda: (emit(0,0,0,-1,0),emit(1,2,512,1,1234)))
    monkeypatch.setattr(demonstration,'HookProcess',fake_process)
    demonstration._hook_main()
    legacy=capsys.readouterr().out.splitlines()
    assert [tuple(map(int,line.split())) for line in legacy]==[(0,0,0,-1),(1,2,512,1)]
    demonstration._hook_main(extra_info=True)
    current=capsys.readouterr().out.splitlines()
    assert [tuple(map(int,line.split())) for line in current]==[(0,0,0,-1,0),(1,2,512,1,1234)]


def test_new_parent_explicitly_selects_v2(monkeypatch):
    from unittest.mock import Mock
    import subprocess
    process=Mock(stdout=io.StringIO('0 0 0 -1 0\n'))
    process.poll.return_value=0
    launch=Mock(return_value=process);monkeypatch.setattr(subprocess,'Popen',launch)
    hook=MouseHook(queue.Queue());hook.start();hook.reader.join(timeout=1);hook.stop()
    assert launch.call_args.args[0][-1]=='--hook-v2' and hook.ready.is_set()


def test_correlated_events_preserve_five_field_consumers_and_flag_authority():
    events=queue.Queue();hook=MouseHook(events)
    hook.process=SimpleNamespace(stdout=io.StringIO(
        '0 0 0 -1 0\n1 2 512 0 0\n2 2 512 1 1234\n3 2 512 0 1234\n'))
    hook._read()
    assert hook.ready.is_set()
    physical,injected,forged=[events.get_nowait() for _ in range(3)]
    assert len(injected)==5 and injected.extra_info==1234
    x,y,message,flags,received_at=injected
    assert (x,y,message,flags)==(2,2,512,1) and received_at>0
    assert classify_input(physical[3])=='user'
    assert classify_input(injected[3])=='injected'
    assert classify_input(forged[3])=='user'  # A matching tag cannot grant injected classification.


def test_legacy_packets_malformed_input_and_full_queue():
    events=queue.Queue(maxsize=1);hook=MouseHook(events)
    hook.process=SimpleNamespace(stdout=io.StringIO('bad\n1 2\n1 2 3 4 5 6\n1 2 512 2\n2 3 512 0\n'))
    hook._read()
    event=events.get_nowait()
    assert isinstance(event,HookEvent) and len(event)==5 and event.extra_info==0
    assert classify_input(event[3])=='injected' and events.empty()
