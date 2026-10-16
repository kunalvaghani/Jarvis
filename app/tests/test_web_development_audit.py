"""Prompt22 owned loopback previews, browser fixtures and fake external services."""
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock,patch

import pytest
from jarvis.development_tools import DevelopmentTools
from jarvis.development_browser import inspect,validate_tests
import tests.test_development_tools as tools_fixture
import tests.test_development as workflow_fixture
import tests.test_development_learning as learning_fixture
import tests.test_development_api as api_fixture

BASE=Path(__file__).resolve().parents[1]
AXE=BASE/'artifacts/projects/development-dashboard/node_modules/axe-core/axe.min.js'
PAGE='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Owned fixture</title><main><h1>Fixture café नमस्ते</h1><button id="save" onclick="document.getElementById('result').textContent='Saved'">Save</button><p role="status" id="result">Ready</p></main></html>'''
TESTS=[{'name':'Save outcome','steps':[{'action':'assert_text','value':'Fixture café नमस्ते'},
    {'action':'click','name':'Save'},{'action':'assert_text','value':'Saved'},
    {'action':'assert_count','role':'button','name':'Save','value':1}]}]


@pytest.fixture
def preview(tmp_path):
    assert AXE.is_file(),'Existing authored fixture axe prerequisite absent; do not install automatically.'
    root=tmp_path/'project';(root/'dist').mkdir(parents=True)
    (root/'dist/index.html').write_text(PAGE,encoding='utf-8')
    axe=root/'node_modules/axe-core/axe.min.js';axe.parent.mkdir(parents=True);shutil.copyfile(AXE,axe)
    tools=DevelopmentTools(BASE);url=tools.start_preview(root,'expo',lambda:False)
    try:yield root,tools,url
    finally:tools.close()


def browser(preview,tests=TESTS):
    root,tools,url=preview
    return tools.inspect(root,url,tests,lambda:False)


def test_JRV_22_001_real_authored_build_and_owned_preview(preview,tmp_path):
    root=BASE/'artifacts/projects/development-dashboard'
    tools=DevelopmentTools(BASE)
    # Dated Prompt 22 evidence is refreshed only on an explicit capture run.
    evidence_dir=(BASE/'artifacts/jarvis-audit/modules/22-web-development'
                  if os.environ.get('JARVIS_CAPTURE_AUDIT_EVIDENCE')=='22' else tmp_path)
    try:
        checks=tools.build(root,'vite',lambda:False)
        assert len(checks)==2 and all(c['exit_code']==0 for c in checks)
        (evidence_dir/'build-checks.json').write_text(
            json.dumps([{'phase':c['phase'],'exit_code':c['exit_code'],'output':c['output']} for c in checks],indent=2),encoding='utf-8')
        evidence=browser(preview)
        assert evidence['goal_verified'] and len(evidence['views'])==3
        assert all(Path(v['screenshot']).is_file() for v in evidence['views'])
        for view in evidence['views']:
            shutil.copyfile(view['screenshot'],evidence_dir/('fixture-'+view['name']+'.png'))
    finally:tools.close()


def test_JRV_22_003_JRV_22_012_busy_port_owned_stop(preview):
    root,tools,url=preview
    with socket.socket() as unrelated:
        unrelated.bind(('127.0.0.1',0));unrelated.listen()
        busy=unrelated.getsockname()[1]
        owned=tools.preview['process'];assert int(url.rsplit(':',1)[1])!=busy
        tools.stop_preview();assert owned.poll() is not None
        assert unrelated.getsockname()[1]==busy


def test_JRV_22_005_remote_api_mocked_in_browser(preview):
    from playwright.sync_api import sync_playwright
    root,tools,url=preview
    (root/'dist/index.html').write_text(PAGE+"<script>fetch('https://api.invalid/items').then(r=>r.json()).then(r=>document.getElementById('result').textContent=r.text)</script>",encoding='utf-8')
    with sync_playwright() as pw:
        b=pw.chromium.launch(channel='chrome',headless=True)
        try:
            c=b.new_context(service_workers='block');seen=[]
            c.route('https://api.invalid/**',lambda r:seen.append(r.request.url) or r.fulfill(json={'text':'Mocked'}))
            p=c.new_page();p.goto(url);p.get_by_text('Mocked',exact=True).wait_for();assert len(seen)==1
        finally:b.close()


def test_JRV_22_006_JRV_22_007_browser_flags_overflow_and_dead_button(preview):
    root,tools,url=preview
    (root/'dist/index.html').write_text(PAGE.replace('onclick="document.getElementById(\'result\').textContent=\'Saved\'"','')+'<style>main{width:900px}</style>',encoding='utf-8')
    result=browser(preview)
    assert not result['goal_verified']
    assert next(v for v in result['views'] if v['name']=='mobile')['horizontal_overflow']
    assert all(not v['scenarios'][0]['passed'] for v in result['views'])


@pytest.mark.parametrize('suffix',['?token=FAKE_SECRET22','#access_token=FAKE_SECRET22','/callback?code=FAKE_SECRET22'])
def test_JRV_22_009_JRV_22_021_auth_url_refused_before_browser(tmp_path,suffix):
    output=tmp_path/'.jarvis/development/run';output.mkdir(parents=True)
    with pytest.raises(ValueError,match='preview|loopback|URL') as error:
        inspect({'project':str(tmp_path),'output':str(output),'url':'http://127.0.0.1:3000'+suffix,'tests':[]})
    assert 'FAKE_SECRET22' not in str(error.value) and not (output/'browser.json').exists()


@pytest.mark.parametrize('case,method',[
 ('JRV-22-014','test_real_command_exit_and_bounded_cancellation'),
 ('JRV-22-018','test_real_owned_preview_close_and_repair_does_not_restart'),
 ('JRV-22-026','test_real_owned_preview_close_and_repair_does_not_restart')])
def test_existing_tools(case,method):tools_fixture.ToolsTests(method).debug()


@pytest.mark.parametrize('case,method',[
 ('JRV-22-020','test_invalid_full_plan_stops_before_generated_writes'),
 ('JRV-22-023','test_explicit_single_file_scope_rejects_extra_plan_files'),
 ('JRV-22-028','test_rejected_verification_is_not_completed')])
def test_existing_workflow(case,method):workflow_fixture.WorkflowTests(method).debug()


def test_JRV_22_024_stale_source_cannot_be_learned():
    learning_fixture.LearningTests('test_model_success_and_stale_code_rejected').debug()


@pytest.mark.parametrize('fault',[ConnectionError('offline'),MemoryError('pressure')])
def test_JRV_22_013_JRV_22_025_JRV_22_030_preview_failure_not_replayed(tmp_path,fault):
    root=tmp_path/'p';(root/'dist').mkdir(parents=True);(root/'dist/index.html').write_text(PAGE,encoding='utf-8')
    tools=DevelopmentTools(tmp_path)
    with patch('jarvis.development_tools.hidden_spawn',return_value=Mock(side_effect=fault)) as spawn:
        with pytest.raises(type(fault)):tools.start_preview(root,'expo',lambda:False)
        assert spawn.call_count==1 and tools.preview is None
    tools.close()


def test_JRV_22_016_missing_dependency_no_install(tmp_path):
    from jarvis.development_tools import binary
    with pytest.raises(ValueError,match='project-local'):binary(tmp_path,'vite')
    assert not (tmp_path/'node_modules').exists()


def test_JRV_22_017_five_independent_status_sessions_twenty_rounds(tmp_path):
    def check(n):
        tool=DevelopmentTools(tmp_path);assert tool.healthy() and tool.preview is None;tool.close();return True
    with ThreadPoolExecutor(max_workers=5) as pool:
        for i in range(20):assert all(pool.map(check,range(i*5,i*5+5)))


def test_JRV_22_022_unicode_dom(preview):
    assert browser(preview)['goal_verified']


@pytest.mark.parametrize('tests',[
 [{'name':'bad action type','steps':[{'action':[]}]}],
 [{'name':'bad','steps':[{'action':'fill','name':'Name'}]}],
 [{'name':'bad','steps':[{'action':'assert_count','name':'Save','value':True}]}],
 [{'name':'bad','steps':[{'action':'click','name':'Save','code':'FAKE_INJECTED'}]}],
 [{'name':'x'*100000,'steps':[{'action':'assert_text','value':'Ready'}]}]])
def test_JRV_22_015_JRV_22_031_malformed_bounded_before_browser(tests):
    with pytest.raises(ValueError):validate_tests(tests)


def test_JRV_22_029_invalid_preview_stack_never_launches(tmp_path):
    tools=DevelopmentTools(tmp_path)
    with patch('jarvis.development_tools.hidden_spawn') as spawn:
        with pytest.raises(ValueError):tools.start_preview(tmp_path,'invalid',lambda:False)
        spawn.assert_not_called()
    tools.close()


def test_browser_context_blocks_service_workers(preview):
    # Observe the actual context kwargs while preserving real Chromium execution.
    from playwright.sync_api import Browser,BrowserContext
    original=Browser.new_context;calls=[];sockets=[];original_socket=BrowserContext.route_web_socket
    def observed(self,*a,**kw):calls.append(kw);return original(self,*a,**kw)
    def observed_socket(self,*a,**kw):sockets.append(a[0]);return original_socket(self,*a,**kw)
    root,tools,url=preview;output=root/'.jarvis/development/direct';output.mkdir(parents=True)
    with patch.object(Browser,'new_context',observed),patch.object(BrowserContext,'route_web_socket',observed_socket):
        assert inspect({'project':str(root),'url':url,'tests':TESTS,'output':str(output)})['goal_verified']
    assert len(calls)==3 and all(c['service_workers']=='block' and c['permissions']==[] for c in calls)
    assert sockets==['**/*']*3


def test_JRV_22_027_benchmark_artifact():
    p=BASE/'artifacts/jarvis-audit/modules/22-web-development/benchmark-summary.json'
    s=json.loads(p.read_text());assert s['equivalent'] and s['external_effects']==0


@pytest.mark.parametrize('case,reason',[
 ('JRV-22-002','Production build previews do not implement a development HMR lifecycle.'),
 ('JRV-22-004','Exit codes and raw build output exist; no benign/regression warning classifier.'),
 ('JRV-22-008','Watchdog stops owned failed preview and requires continuation; no safe automatic restart contract.'),
 ('JRV-22-010','Browser auth context is isolated; project build/server code executes as the host user, without filesystem confinement.'),
 ('JRV-22-011','Lock/source guards and reviewed install exist; no reproducible API-break compatibility upgrade oracle.'),
 ('JRV-22-019','Owned jobs stop on process exit; no durable preview crash-resume protocol.'),
 ('JRV-22-032','Raw build/browser diagnostics may contain credentials; complete redaction/trace contract missing.')],ids=lambda v:v)
def test_missing_contract(case,reason):pytest.skip('BLOCKED: '+reason)
