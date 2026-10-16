"""Owned background worker -> pinned static knowledge -> restart -> coding-context readback."""
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock,patch

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from jarvis import repo_learning as r
from jarvis.agent_context import learned_references
from tests.test_repo_learning import LearningTests,Summary


def main():
    start=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='jarvis-repo-journey-') as tmp:
        base=Path(tmp);actions=SimpleNamespace(base=base,report=Mock(),memory=SimpleNamespace(vault=base/'vault',record=Mock()))
        http=LearningTests().http_for(LearningTests.INFO)
        learner=r.RepoLearner(actions,{},http=http,model_chat=Summary());actions.repo_learner=learner
        forbidden=Mock(side_effect=AssertionError('real transport/process forbidden'))
        with patch('requests.sessions.Session.request',forbidden),patch('subprocess.Popen',forbidden):
            reply=r.execute(actions,r.parse_command('learn demo/snake'),lambda:False)
            assert 'Learning' in reply
            deadline=time.monotonic()+5
            while learner.busy() and time.monotonic()<deadline:time.sleep(.01)
            assert learner.known('demo/snake')
            data=learner.knowledge('demo/snake');assert data['commit']=='a'*40 and data['trace_id']
            assert data['verification']['executed_tests'] is False
            assert 'Commit: '+data['commit'] in (learner.vault/'demo__snake.md').read_text(encoding='utf-8')
            learner.close();learner.thread.join(2);assert not learner.thread.is_alive()
            offline=Mock();offline.get.side_effect=AssertionError('offline restart cannot query GitHub')
            again=r.RepoLearner(actions,{},http=offline,model_chat=Mock())
            try:
                with patch.dict(r.REGISTRY,{'learner':again}):refs=learned_references('create a snake game canvas')
                assert refs and refs[0]['commit']==data['commit'] and refs[0]['code_excerpts']
                assert refs[0]['reuse_review_required'] and refs[0]['url']=='https://github.com/demo/snake'
                assert sum(len(e['excerpt']) for e in refs[0]['code_excerpts'])<=3500
                offline.get.assert_not_called();forbidden.assert_not_called()
            finally:again.close()
        # Exercise the separate trusted Git acquisition boundary using only an owned fixture.
        from jarvis import repo_acquisition as acq
        project=base/'owned-project';project.mkdir()
        assert project.resolve().is_relative_to(base.resolve())
        acq.git(['init','--template=',str(project)])
        (project/'main.py').write_text('raise RuntimeError("never import this fixture")\ndef inspect_only(): return 1\n')
        acq.git(['-C',str(project),'add','main.py'])
        acq.git(['-C',str(project),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','owned fixture'])
        commit=acq.git(['-C',str(project),'rev-parse','HEAD']).decode().strip()
        snapshot=acq.acquire(str(project),base/'snapshot-vault')
        assert snapshot['commit']==commit and snapshot['hashes']['main.py']
        try:acq.git(['clone','--no-checkout',str(project),str(base/'refused-clone')])
        except ValueError:pass  # File transport remains disabled even for an owned source.
        else:raise AssertionError('Unsafe file transport unexpectedly admitted')
    result={'date':'2026-10-16 IST','passed':True,'seconds':time.perf_counter()-start,'network_calls':0,'repository_code_executions':0,
        'scope':'Actual command/background worker, fake GitHub/summary, atomic knowledge/index/note readback, Stop, restart and agent_context references. Separate real Git init/commit/rev-parse/local acquisition and denied file-transport clone on an owned fixture. No account/model/downloaded-code execution/ability install.',
        'git_fixture_commit':commit,'steps':['command','background learn','commit/hash/trace readback','Obsidian-note readback','owned worker Stop','restart','coding-context offline reference','trusted Git read/local source snapshot','unsafe clone transport denied']}
    (BASE/'artifacts/jarvis-audit/modules/18-repo-learning/repository-journey.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
