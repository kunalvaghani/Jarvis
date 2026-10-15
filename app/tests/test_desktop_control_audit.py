"""Prompt13: owned fake UIA/Win32/pipe transports, never user desktop input."""
from types import SimpleNamespace
from unittest.mock import Mock,patch
import json
import pytest
from jarvis.execution_adapters import Prepared,Unsupported
from jarvis.execution_router import execute,UncertainAction


class Clock:
    def __init__(self):self.value=0.0
    def __call__(self):return self.value
    def sleep(self,n):self.value+=n


def route(providers,**kw):
    clock=Clock()
    return execute({'operation':'activate','value':'Apply'},None,{'name':'Apply','role':'Button'},None,
                   kw.pop('guard',lambda:None),providers=providers,clock=clock,sleep=clock.sleep,**kw)


def provider(call=None,**kw):
    return SimpleNamespace(name='ufo',prepare=Mock(return_value=Prepared(call or Mock(),**kw)))


def test_preparation_access_denied_never_falls_through():
    first=SimpleNamespace(name='ufo',prepare=Mock(side_effect=PermissionError('secure desktop')))
    second=provider()
    with pytest.raises(PermissionError):route([first,second])
    second.prepare.assert_not_called()


def test_native_com_access_denied_never_falls_through():
    from comtypes import COMError
    first=SimpleNamespace(name='ufo',prepare=Mock(side_effect=COMError(-2147024891,'Access denied',None)))
    second=provider()
    with pytest.raises(COMError):route([first,second])
    second.prepare.assert_not_called()


def test_exception_payload_not_returned_in_receipt_or_message():
    secret='password=fake-private-123456'
    with pytest.raises(UncertainAction) as failure:route([provider(Mock(side_effect=RuntimeError(secret)))])
    assert secret not in str(failure.value)
    assert secret not in json.dumps(failure.value.receipt)
    assert len(failure.value.receipt['trace_id'])==32


def test_oversized_request_never_enters_guard_or_provider():
    p=provider();guard=Mock()
    with pytest.raises(ValueError):
        execute({'operation':'activate','value':'x'*100001},None,{'role':'Button','name':'Apply'},None,guard,providers=[p])
    p.prepare.assert_not_called();guard.assert_not_called()


def test_invalid_pointer_configuration_fails_closed(tmp_path):
    from jarvis.jarvis_pointer import enabled
    folder=tmp_path/'config';folder.mkdir();path=folder/'config.json'
    for text in ('{','[]','{"cursor": {"physical_clicks": "false"}}','{"cursor": false}'):
        path.write_text(text)
        assert enabled(tmp_path) is False


def test_pointer_admission_runs_after_mouse_idle_wait():
    from jarvis.jarvis_pointer import tap
    from tests.test_jarvis_pointer import FakeUser
    user=FakeUser();admit=Mock(side_effect=ValueError('target moved'))
    with patch('jarvis.jarvis_pointer.wait_for_idle_mouse',return_value=True),patch('jarvis.jarvis_pointer._initialized',[False]):
        with pytest.raises(ValueError,match='target moved'):tap(10,20,user=user,sleep=lambda _:None,admit=admit)
    admit.assert_called_once()
    assert not any(c[0]=='touch' for c in user.calls)


def test_touch_restores_thread_dpi_context():
    from jarvis.jarvis_pointer import tap
    from tests.test_jarvis_pointer import FakeUser
    user=FakeUser();user.SetThreadDpiAwarenessContext=Mock(return_value=123)
    with patch('jarvis.jarvis_pointer.wait_for_idle_mouse',return_value=True),patch('jarvis.jarvis_pointer._initialized',[False]):
        tap(10,20,user=user,sleep=lambda _:None)
    assert user.SetThreadDpiAwarenessContext.call_count==2
    assert user.SetThreadDpiAwarenessContext.call_args.args[0]==123


def test_malformed_worker_frame_stops_owned_worker_without_replay():
    from jarvis.ui_transport import UITransport
    from tests.test_automation_upgrade import FakeProcess
    process=FakeProcess(lambda _:[]);worker=UITransport(factory=Mock(return_value=process))
    try:
        with pytest.raises(RuntimeError,match='without replay'):worker.request({'operation':'activate'})
        assert len(process.requests)==1 and process.code==-1
    finally:worker.close()


def pointer_fixture(moved=False):
    """Exercise production provider→tap with simulated150% physical geometry."""
    from contextlib import ExitStack
    from jarvis.execution_adapters import JarvisPointer
    from tests.test_jarvis_pointer import FakeUser
    class Element:
        __module__='pywinauto.audit_fixture'
        element_info=SimpleNamespace(runtime_id=[13])
        bounds=[150,150,450,300]
        def rectangle(self):
            l,t,r,b=self.bounds
            return SimpleNamespace(left=l,top=t,right=r,bottom=b,width=lambda:r-l,height=lambda:b-t)
        def is_visible(self):return True
        def is_enabled(self):return True
    element=Element();user=FakeUser()
    def wait(*args):
        if moved:element.bounds=[500,150,800,300]
        return True
    with ExitStack() as stack:
        stack.enter_context(patch('jarvis.jarvis_pointer.enabled',return_value=True))
        stack.enter_context(patch('jarvis.jarvis_pointer.user32',return_value=user))
        stack.enter_context(patch('jarvis.jarvis_pointer.wait_for_idle_mouse',side_effect=wait))
        stack.enter_context(patch('jarvis.jarvis_pointer._initialized',[False]))
        stack.enter_context(patch('win32gui.GetForegroundWindow',return_value=123))
        stack.enter_context(patch('win32gui.IsWindow',return_value=True))
        stack.enter_context(patch('win32gui.WindowFromPoint',return_value=123))
        stack.enter_context(patch('win32gui.GetAncestor',return_value=123))
        stack.enter_context(patch('pywinauto.Desktop',return_value=SimpleNamespace(from_point=lambda *args:element)))
        stack.enter_context(patch('jarvis.execution_adapters.selection',side_effect=Unsupported('no pattern')))
        prepared=JarvisPointer().prepare(element,{'id':[13],'role':'Button'}, {'operation':'activate'},SimpleNamespace(handle=123))
        if moved:
            with pytest.raises(ValueError,match='moved'):prepared.call()
            assert not any(c[0]=='touch' for c in user.calls)
        else:
            assert prepared.call() is True
            assert [(c[2],c[3]) for c in user.calls if c[0]=='touch']==[(300,225),(300,225)]


def test_real_pointer_adapter_rechecks_after_idle():pointer_fixture(moved=True)


def test_pointer_uses_physical_coordinates_without_double_scaling():pointer_fixture()


def old_case(module,cls,name):
    import importlib
    getattr(importlib.import_module('tests.'+module),cls)(name).debug()


@pytest.mark.parametrize('case_id',[f'JRV-13-{n:03}' for n in range(1,33)])
def test_catalog(case_id,tmp_path):
    n=int(case_id[-3:])
    if n==1:
        value=SimpleNamespace(CurrentValue='');call=Mock(side_effect=lambda:setattr(value,'CurrentValue','hello'))
        p=provider(call,read=lambda:value.CurrentValue,expected='hello')
        guard=Mock();clock=Clock()
        result=execute({'operation':'fill_text','content':'hello'},None,{'name':'Notepad','role':'Edit'},SimpleNamespace(handle=1),guard,providers=[p],clock=clock,sleep=clock.sleep)
        assert result['verified'] and value.CurrentValue=='hello' and guard.call_count>=3
        call.assert_called_once()
    elif n in (2,9):
        p=provider();guard=Mock(side_effect=[None,ValueError('focus changed or locked')])
        with pytest.raises(ValueError):route([p],guard=guard)
        p.prepare.return_value.call.assert_not_called()
        from jarvis.ui_worker import routed
        with patch('win32gui.IsWindow',return_value=True),patch('win32gui.GetForegroundWindow',return_value=456 if n==2 else 0),patch('win32process.GetWindowThreadProcessId',return_value=(1,99)):
            with pytest.raises(ValueError,match='focus changed'):
                routed({'operation':'fill_text','content':'hello'},Mock(),Mock(),{'role':'Edit','name':'Notepad'},123)
    elif n==3:
        old_case('test_ui_controls','UITests','test_duplicate_labels_require_number_and_do_not_click')
        from jarvis.ui_controls import UIControls
        import os
        user=Mock();user.GetForegroundWindow.return_value=222
        user.GetWindowThreadProcessId.side_effect=lambda hwnd,pid:setattr(pid._obj,'value',os.getpid()+100)
        desktop=SimpleNamespace(user=user,target=111)
        # Both target handles may have the title Settings; identity comes from foreground HWND, never title.
        assert UIControls(desktop)._handle()==222
    elif n==4:
        pointer_fixture()
        pytest.skip('BLOCKED: live150% DPI/multi-monitor click validation not authorized; no personal display settings changed. Physical-coordinate fixture passed separately.')
    elif n==5:
        first=SimpleNamespace(name='ufo',prepare=Mock(side_effect=Unsupported('missing')))
        second=SimpleNamespace(name='windows-mcp',prepare=Mock(return_value=Prepared(Mock(),lambda:True,True)))
        assert route([first,second])['provider']=='windows-mcp'
        second.prepare.return_value.call.assert_called_once()
    elif n==6:
        providers=[SimpleNamespace(name=name,prepare=Mock(side_effect=Unsupported('missing'))) for name in ('ufo','windows-mcp','cua')]
        with pytest.raises(ValueError,match='No input issued'):route(providers)
        assert all(p.prepare.call_count==1 for p in providers)
    elif n==7:
        test_preparation_access_denied_never_falls_through()
        test_native_com_access_denied_never_falls_through()
        pytest.skip('BLOCKED: real UAC/secure-desktop validation would require elevation/personal OS state changes; no bypass attempted. Permission-denial fixture passed separately.')
    elif n in (8,14):
        old_case('test_automation_upgrade','TransportTests','test_timeout_lost_response_is_not_retried')
        p=provider(Mock(side_effect=TimeoutError('hung app')));last=provider()
        with pytest.raises(UncertainAction):route([p,last])
        p.prepare.return_value.call.assert_called_once();last.prepare.assert_not_called()
    elif n==10:
        old_case('test_ui_controls','UITests','test_changed_controls_invalidate_number')
    elif n in (11,24):test_real_pointer_adapter_rechecks_after_idle()
    elif n==12:
        old_case('test_jarvis_pointer','PointerTests','test_no_click_while_the_user_holds_a_mouse_button')
    elif n==13:
        import requests
        with patch.object(requests.sessions.Session,'request',side_effect=ConnectionError) as net:
            assert route([provider(read=lambda:True,expected=True)])['verified']
            net.assert_not_called()
    elif n in (15,30):test_malformed_worker_frame_stops_owned_worker_without_replay()
    elif n==16:
        first=SimpleNamespace(name='ufo',prepare=Mock(side_effect=ImportError('missing component')))
        second=provider(read=lambda:True,expected=True)
        assert route([first,second])['verified']
    elif n==17:
        from concurrent.futures import ThreadPoolExecutor
        from jarvis.ui_transport import UITransport
        from tests.test_automation_upgrade import FakeProcess
        process=FakeProcess();worker=UITransport(factory=Mock(return_value=process))
        try:
            with ThreadPoolExecutor(max_workers=5) as pool:
                for _ in range(20):assert all(r['ready'] for r in pool.map(lambda _:worker.request({'operation':'list'}),range(5)))
            assert len(process.requests)==100 and len({r['id'] for r in process.requests})==100
        finally:worker.close()
    elif n==18:old_case('test_automation_upgrade','TransportTests','test_cancel_after_dispatch_kills_only_owned_worker_and_uses_backoff')
    elif n==19:old_case('test_automation_upgrade','TransportTests','test_stop_prevents_restart_or_new_dispatch')
    elif n in (20,28):old_case('test_execution_router','DirectTests','test_sensitive_dialog_does_not_bypass_existing_approvals')
    elif n in (21,32):test_exception_payload_not_returned_in_receipt_or_message()
    elif n==22:
        content='café हिन्दी 😀';value=SimpleNamespace(CurrentValue='')
        from jarvis.execution_adapters import UFO
        value.SetValue=Mock(side_effect=lambda text:setattr(value,'CurrentValue',text))
        with patch('jarvis.execution_adapters.pattern',return_value=value):
            prepared=UFO().prepare(None,{}, {'operation':'fill_text','content':content},None);prepared.call()
        assert prepared.read()==content;value.SetValue.assert_called_once_with(content)
    elif n==23:
        from jarvis.commands import parse
        with pytest.raises(ValueError,match='negated'):parse("don't open notepad")
    elif n==25:
        p=SimpleNamespace(name='ufo',prepare=Mock(side_effect=MemoryError('pressure')));second=provider(read=lambda:True,expected=True)
        assert route([p,second])['verified']
        second.prepare.return_value.call.assert_called_once()
    elif n==26:
        old_case('test_execution_router','RoutingTests','test_partial_failure_never_clicks_again')
        old_case('test_execution_router','RoutingTests','test_already_present_state_does_not_issue_input')
    elif n==27:
        from pathlib import Path
        summary=json.loads((Path(__file__).resolve().parents[1]/'artifacts/jarvis-audit/modules/13-desktop-control/benchmark-summary.json').read_text())
        assert summary['effects_verified'] and all(summary['results'][v+'_'+m]['samples']==count for v in ('before','after') for m,count in [('cold',5),('warm',20)])
    elif n==29:test_invalid_pointer_configuration_fails_closed(tmp_path)
    elif n==31:test_oversized_request_never_enters_guard_or_provider()
    else:raise AssertionError(case_id)
