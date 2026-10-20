"""Fresh IR-004 reproduction in a disposable >260-character Windows lab path."""
from pathlib import Path
import sys

APP = Path('D:\\Kunals GitHub Repo\\LocalGithub\\Jarvis-e2e-e5af0e7\\app')
sys.path.insert(0, str(APP))
from tests.test_phase06_controlled_evolution import canon, research_for, candidate, repo_state


def test_IR_004_deep_owned_worktree_preserves_canonical_source(canon, tmp_path):
    deep = tmp_path.joinpath(*['owned-' + 'x' * 64 for _ in range(4)])
    deep.mkdir(parents=True)
    assert len(str(deep)) > 260
    before = repo_state(canon)
    research = research_for(canon, deep)
    identifier, parent = candidate(research, {'base_seconds': 0.1, 'max_seconds': 2.0})
    commit = research.lab.create_candidate(identifier, parent['lab_commit'], 'read_retry_backoff',
        {'base_seconds': 0.1, 'max_seconds': 2.0}, 'deep path fixture')
    checkout = research.lab.worktree(identifier, commit)
    try:
        assert len(str(checkout / 'jarvis/task_recovery.py')) > 260
        assert (checkout / 'jarvis/task_recovery.py').is_file()
        assert 'base_seconds' in (checkout / 'jarvis/task_recovery.py').read_text(encoding='utf-8')
        assert repo_state(canon) == before
    finally:
        research.lab.remove_worktree(checkout)
