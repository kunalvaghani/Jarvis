"""MASTER prompt cases: deterministic owned fixtures, no account/UI effects."""
import math
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from jarvis.cognition import Cognition, Percept
from jarvis.commands import Command, parse
from jarvis.deliberation import Deliberation
from jarvis.engine import Engine
from jarvis.self_evolution import CapabilityGapDetector

def actions(root):
    return SimpleNamespace(base=root,current_item=None,whatsapp_prompts=[],pending_tasks=[],
        session_style={},approvals_waiting=0,memory=None,command_history=[])

@pytest.mark.parametrize('age',[-1e12,-100,0,1e12])
def test_AUD_CLOCK_decay_is_bounded_under_clock_changes(age):
    percept=Percept('screen','vision','Fixture',.85)
    percept.at=1000
    weight=percept.weight(1000+age)
    assert math.isfinite(weight) and 0<=weight<=percept.salience

def test_AUD_ADMISSION_old_voice_does_not_starve_fresh_window(tmp_path):
    mind=Cognition(actions(tmp_path))
    for i in range(200):
        mind.perceive('you','speech',f'Old {i}',1)
        mind.percepts[-1].at=time.time()-3600
    mind.perceive_window('Fresh application')
    mind.tick()
    assert mind.attention[0].content=='Fresh application'

@pytest.mark.parametrize('value',[None,[],{'attempts':'broken'}, {'attempts':3,'successes':float('nan')}])
def test_AUD_HISTORY_all_consumers_tolerate_corruption(tmp_path,value):
    a=actions(tmp_path)
    mind=a.cognition=Cognition(a)
    mind.stats={'task':value}
    assert isinstance(mind.explain(mind.predict(Command('task','Safe fixture'))),str)
    opinion=Deliberation(a,{'enabled':False}).form_opinion('Safe fixture',Command('task','Safe fixture'),lambda:False)
    assert math.isfinite(opinion['confidence'])
    assert isinstance(CapabilityGapDetector(a).detect(),list)

def test_AUD_STOP_serializes_with_inflight_feed():
    entered,release,reset_done=threading.Event(),threading.Event(),threading.Event()
    engine=Engine(lambda _:None,lambda *_:None)
    def feed(*args): entered.set();assert release.wait(3)
    engine._feed=feed
    first=threading.Thread(target=engine.feed,args=('fixture',))
    def stop():engine.reset();reset_done.set()
    first.start();assert entered.wait(1)
    second=threading.Thread(target=stop);second.start()
    try:
        assert not reset_done.wait(.05),'Stop reset races with in-flight feed'
    finally:
        release.set();first.join(2);second.join(2)
    assert reset_done.is_set() and not engine.active

@pytest.mark.parametrize('text,kind', [('pause','click_control'),('PAUSE','click_control'),
    (' volume up ','spotify_volume'),('open Chrome','open'),('open\tChrome','open')])
def test_AUD_REFLEX_metamorphic_preserves_handlers(text,kind):
    assert parse(text).kind==kind

def test_AUD_STOP_no_dispatch_after_reset_without_wake():
    dispatched=[]
    engine=Engine(dispatched.append,lambda *_:None)
    engine.activate(now=100)
    engine.reset()
    engine.feed('open Chrome',True,now=101)
    assert dispatched==[]
