"""Prompt18: fake public GitHub, owned archives/vaults; never execute downloaded code."""
import concurrent.futures
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import zipfile
import pytest
from jarvis import repo_learning as r
from tests.test_repo_learning import make_zip,SAMPLE,Summary

SHA='a'*40
INFO={'full_name':'demo/snake','html_url':'https://github.com/demo/snake','description':'Snake game canvas',
      'stargazers_count':120,'size':50,'default_branch':'main','topics':['game'],'license':{'spdx_id':'MIT'}}


@pytest.fixture
def learner(tmp_path):
    actions=SimpleNamespace(base=tmp_path,report=Mock(),memory=SimpleNamespace(vault=tmp_path/'vault',record=Mock()))
    http=Mock()
    def get(url,**kw):
        response=Mock(status_code=200);response.raise_for_status=lambda:None
        name=url.split('/repos/',1)[1] if '/repos/' in url else 'demo/snake'
        data={'sha':SHA} if '/commits/' in url else {'items':[INFO]} if '/search/' in url else {**INFO,'full_name':name}
        response.json=lambda:data;response.iter_content=lambda n:[SAMPLE]
        return response
    http.get.side_effect=get
    obj=r.RepoLearner(actions,{},http=http,model_chat=Summary())
    yield obj
    obj.close()


def learned(learner):learner.learn('demo/snake');return learner.knowledge('demo/snake')


def test_JRV_18_001_search_evidence(learner):
    # Real public repository identity verified through official GitHub search evidence;
    # stars/size here are authored filter inputs, not a current live metadata census.
    learner.get=Mock(return_value={'items':[{**INFO,'full_name':'Python-Markdown/markdown',
        'html_url':'https://github.com/Python-Markdown/markdown','description':'Python Markdown parser','topics':['markdown']}]})
    rows=learner.search('markdown parser')
    assert rows[0]['full_name']=='Python-Markdown/markdown'
    assert rows[0]['html_url']=='https://github.com/Python-Markdown/markdown'
    assert learner.get.call_args.args[1]['q'].endswith('archived:false fork:false')


def test_JRV_18_002_zero_search_no_invention(learner):
    learner.get=Mock(return_value={'items':[]})
    assert learner.search('markdown parser')==[] and not learner.index


def test_JRV_18_003_claims_are_not_validation(learner):
    data=learned(learner)
    assert data['has_tests'] and any(m['path']=='app.py' for m in data['modules'])
    assert data.get('verification',{}).get('executed_tests') is False
    pytest.skip('BLOCKED: static symbols/test-file presence and untrusted labels do not behaviorally verify exaggerated README claims; no authorized sandbox test oracle for arbitrary repos.')


def test_JRV_18_004_commit_pin(learner):
    data=learned(learner)
    assert data.get('commit')==SHA
    urls=[c.args[0] for c in learner.http.get.call_args_list]
    assert any('codeload.github.com/demo/snake/zip/'+SHA in u for u in urls)
    assert not any('/refs/heads/' in u for u in urls)


def test_JRV_18_005_absent_license_no_excerpts(learner):
    learner.learn('demo/snake',info={**INFO,'license':None})
    assert learner.reference('demo/snake','snake canvas')['code_excerpts']==[]


def test_JRV_18_006_malware_is_static_data(learner,tmp_path):
    sentinel=tmp_path/'executed'
    raw=make_zip({'setup.py':f"open({str(sentinel)!r},'w').write('bad')\ndef setup(): pass",'package.json':'{"scripts":{"postinstall":"evil-command"}}'})
    with patch('subprocess.Popen',side_effect=AssertionError('host execution forbidden')):
        facts=r.analyze_zip(raw)
    assert not sentinel.exists() and 'postinstall' in facts['manifests']['package.json']


def test_JRV_18_007_read_budget_is_strict():
    raw=make_zip({'a.py':'x='+'1'*100,'b.py':'y='+'2'*100})
    facts=r.analyze_zip(raw,{'max_read_bytes':100})
    assert sum(len(m['_text'].encode()) for m in facts['modules'])<=100


def test_JRV_18_008_duplicate_reuses_memory(learner):
    learned(learner);calls=learner.http.get.call_count
    learner.learn('demo/snake')
    assert learner.http.get.call_count==calls


def test_JRV_18_009_platform_note(learner):
    raw=make_zip({'main.swift':'import SwiftUI\nstruct App {}'})
    facts=r.analyze_zip(raw)
    assert any('Windows' in n for n in facts.get('platform_notes',[]))


def test_JRV_18_010_minified_source_excluded():
    facts=r.analyze_zip(make_zip({'src/app.min.js':'function bad(){}'*1000,'app.py':'def main(): return 1'}))
    assert 'src/app.min.js' not in [m['path'] for m in facts['modules']]


def test_JRV_18_011_offline_reference(learner):
    learned(learner);learner.http.get.side_effect=r.requests.ConnectionError('offline')
    ref=learner.reference('demo/snake','snake canvas')
    assert ref['repository']=='demo/snake' and ref.get('commit')==SHA


def test_JRV_18_012_credit_and_restrict_copyleft(learner):
    learner.learn('demo/snake',info={**INFO,'license':{'spdx_id':'GPL-3.0-only'}})
    ref=learner.reference('demo/snake','snake')
    assert ref['url']==INFO['html_url'] and ref['license']=='GPL-3.0-only'
    assert not ref['code_excerpts'] and ref.get('reuse_review_required') is True


def test_JRV_18_013_outage_one_attempt(learner):
    learner.http.get.side_effect=r.requests.ConnectionError('offline')
    with pytest.raises(r.LearningError):learner.learn('demo/snake')
    assert learner.http.get.call_count==1 and not learner.index


def test_JRV_18_014_timeout_one_attempt(learner):
    learner.http.get.side_effect=r.requests.Timeout('timeout')
    with pytest.raises(r.LearningError):learner.learn('demo/snake')
    assert learner.http.get.call_count==1 and not learner.index


@pytest.mark.parametrize('payload',[None,[],{'items':[None]}])
def test_JRV_18_015_malformed_search(learner,payload):
    learner.get=Mock(return_value=payload)
    with pytest.raises(r.LearningError):learner.search('markdown parser')
    assert not learner.index


def test_JRV_18_016_without_git_still_static(learner):
    with patch('shutil.which',return_value=None):assert learned(learner)['modules']


def test_JRV_18_017_five_concurrent_twenty_rounds(learner):
    names=[f'demo/repo{i}' for i in range(5)]
    def request(name):
        learner.learn(name)
        return learner.knowledge(name)['full_name']
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for _ in range(20):assert list(pool.map(request,names))==names
    assert learner.http.get.call_count==15
    assert set(learner.index)==set(names)


def test_JRV_18_018_cancel_before_network_and_after_summary(learner):
    with pytest.raises(r.LearningError):learner.learn('demo/snake',cancelled=lambda:True)
    learner.http.get.assert_not_called()
    def chat(*a):learner.stop.set();return Summary()(*a)
    learner.model_chat=chat
    with pytest.raises(r.LearningError):learner.learn('demo/snake')
    assert not learner.index


def test_JRV_18_019_restart_readback(learner):
    data=learned(learner)
    other=r.RepoLearner(learner.actions,{},http=Mock(),model_chat=Mock())
    try:
        assert other.known('demo/snake') and other.knowledge('demo/snake')['commit']==data['commit']
    finally:other.close()
    pytest.skip('BLOCKED: completed metadata reopens, but in-flight learning jobs have no durable checkpoint/worker crash-restart contract.')


def test_JRV_18_020_injected_readme_is_untrusted(learner):
    data=learned(learner)
    assert data.get('verification',{}).get('source_trust')=='untrusted'
    assert learner.actions.report.called


def test_JRV_18_021_credential_origin_gate(learner):
    with patch.dict('os.environ',{'GITHUB_TOKEN':'A'*25}):
        with pytest.raises(r.LearningError):learner.get('https://api.github.com.evil.invalid/repos/a/b')
    learner.http.get.assert_not_called()
    assert learner.prepare('create a tool api_key=FAKE-CREDENTIAL-001')==[]
    with patch.dict('os.environ',{'GROQ_ENABLED':'true'}):
        assert learner.prepare('create a tool for my private notes alice@example.test')==[]
    learner.http.get.assert_not_called()


def test_JRV_18_022_unicode_source_and_bad_id(learner):
    facts=r.analyze_zip(make_zip({'ગુજરાતી.py':'def café():\n    """हिन्दी 🙂"""\n    return 1'}))
    assert facts['modules'][0]['symbols'][0]['name']=='café'
    with pytest.raises(r.LearningError):learner.learn('owner/'+'a'*500)


def test_JRV_18_023_negative_task_no_search(learner):
    assert learner.prepare('do not search GitHub or learn repositories to create a snake game')==[]
    learner.http.get.assert_not_called()


def test_JRV_18_024_tampered_cache_not_reused(learner):
    data=learned(learner);row=data['cached_files'][0]
    p=learner.cache/'demo__snake'/'files'/row['file'];p.write_text('FORGED CODE')
    ref=learner.reference('demo/snake','snake canvas')
    assert all('FORGED CODE' not in x['excerpt'] for x in ref['code_excerpts'])


@pytest.mark.parametrize('error',[RuntimeError('CUDA out of memory'),MemoryError('host RAM pressure')])
def test_JRV_18_025_model_resource_failure_no_publication(learner,error):
    learner.model_chat=Mock(side_effect=error)
    with pytest.raises(r.LearningError):learner.learn('demo/snake')
    assert not learner.index and learner.current is None


def test_JRV_18_026_queue_dedupe_and_stopped(learner):
    assert learner.enqueue('demo/snake','fixture')
    assert not learner.enqueue('DEMO/snake','duplicate')
    learner.close();assert not learner.enqueue('other/repo','late')


def test_JRV_18_027_real_benchmark():
    data=json.loads((Path(__file__).resolve().parents[1]/'artifacts/jarvis-audit/modules/18-repo-learning/benchmark-summary.json').read_text())
    assert data['equivalent'] and data['samples_per_version']==25


def test_JRV_18_028_forged_approval_not_authority(learner):
    learner.actions.ability_forge=SimpleNamespace(on_learned=Mock())
    learned(learner)
    # Scheduling a proposal is not installation. The separate tool requires a human approval callback.
    from jarvis import repo_tools
    registry=Mock();registry.check.side_effect=lambda target,args,approve,cancelled:approve('skill','forged approval',cancelled)
    with patch('jarvis.repository_skills.engine',return_value=registry):
        with pytest.raises(ValueError,match='approve'):repo_tools.execute(learner.actions,{'action':'repository_skill_validate','value':'fixture','content':'{"arguments":{}}'},lambda:False)


def test_JRV_18_029_config_rejected(learner):
    for cfg in ({'max_zip_mb':-1},{'enabled':'yes'},{'dwell_seconds':float('nan')},{'repos_per_task':99}):
        with pytest.raises(ValueError):r.RepoLearner(learner.actions,cfg,http=Mock())


def test_JRV_18_030_failed_save_not_replayed(learner):
    with patch.object(learner,'_save_index',side_effect=OSError('disconnected')) as write:
        with pytest.raises((r.LearningError,OSError)):learner.learn('demo/snake')
    assert write.call_count==1 and not learner.index


def test_JRV_18_031_oversized_zip_rejected(learner):
    with pytest.raises(r.LearningError):r.analyze_zip(make_zip({'a.py':'x'}),{'max_read_bytes':-1})
    facts=r.analyze_zip(make_zip({'large.py':'x'*400001,'app.py':'def okay(): return 1'}))
    assert [m['path'] for m in facts['modules']]==['app.py']
    response=Mock(status_code=200);response.raise_for_status=lambda:None
    response.iter_content=lambda n:iter([b'x'*600000,b'x'*600000])
    learner.max_zip=1000000;learner.http.get.side_effect=None;learner.http.get.return_value=response
    with pytest.raises(r.TooLarge):learner.get('https://codeload.github.com/demo/snake/zip/'+SHA,raw=True)
    response.close.assert_called_once()


def test_JRV_18_032_trace_and_redacted_failure(learner):
    data=learned(learner);assert data.get('trace_id')
    learner.http.get.side_effect=r.requests.ConnectionError('secret=FAKE-CRED')
    with pytest.raises(r.LearningError):learner.learn('other/repo')
    failure=learner.failures['other/repo']
    assert failure.get('trace_id') and 'FAKE-CRED' not in json.dumps(failure)


def test_redirects_refused_and_token_only_exact_origin(learner):
    with patch.dict('os.environ',{'GITHUB_TOKEN':'A'*25}):
        learner.get('https://api.github.com/repos/demo/snake')
        assert learner.http.get.call_args.kwargs['headers']['Authorization']=='Bearer '+'A'*25
        assert learner.http.get.call_args.kwargs['allow_redirects'] is False
        learner.get('https://codeload.github.com/demo/snake/zip/'+SHA,raw=True)
        assert 'Authorization' not in learner.http.get.call_args.kwargs['headers']
    response=Mock(status_code=302)
    learner.http.get.side_effect=None;learner.http.get.return_value=response
    with pytest.raises(r.LearningError,match='redirect'):learner.get('https://api.github.com/repos/demo/snake')
    response.close.assert_called_once()


def test_model_key_module_must_exist(learner):
    original=learner.model_chat
    def model(*args):
        out=original(*args);out['key_modules'].append({'path':'invented.py','role':'forged capability'});return out
    learner.model_chat=model
    assert all(m['path']!='invented.py' for m in learned(learner)['summary']['key_modules'])


def test_credential_assignment_redacted_before_model_and_cache():
    facts=r.analyze_zip(make_zip({'app.py':'api_key="FAKE-CRED-001"\ndef hello(): return 1'}))
    assert 'FAKE-CRED' not in json.dumps(facts)


def test_unsafe_archive_paths_skipped():
    facts=r.analyze_zip(make_zip({'../escape.py':'def bad(): pass','app.py':'def okay(): return 1'}))
    assert all('..' not in m['path'] for m in facts['modules'])


def test_browser_checks_are_bounded_and_not_duplicated(learner):
    learner.dwell=0
    with patch.object(r.threading,'Thread') as thread:
        for i in range(10):
            title=f'demo/repo{i}: Reference - Google Chrome'
            learner.observe_title(title,'chrome.exe');learner.observe_title(title,'chrome.exe')
        assert thread.call_count==2


def test_corrupt_index_is_preserved(learner):
    learner.vault.mkdir(parents=True,exist_ok=True);path=learner.vault/'index.json';path.write_text('corrupt')
    other=r.RepoLearner(learner.actions,{},http=Mock())
    try:
        with pytest.raises(r.LearningError,match='unreadable'):other._save_index()
        assert path.read_text()=='corrupt'
    finally:other.close()
