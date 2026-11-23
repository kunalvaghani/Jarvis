"""Optional actor compatibility never relaxes the paused-project/run barrier."""
import json
from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
from jarvis import campaign_pause
from jarvis.runtime_scope import optional_actor_base

@pytest.mark.parametrize('actor',[SimpleNamespace(),SimpleNamespace(base=None),SimpleNamespace(base=object()),Mock()])
def test_optional_context_is_not_coerced_to_a_path(actor):
    assert optional_actor_base(actor) is None

def test_real_pathlike_context_is_retained(tmp_path):
    assert optional_actor_base(SimpleNamespace(base=tmp_path))==str(tmp_path)

def test_missing_optional_context_allows_normal_coding_but_protected_projects_still_stop(tmp_path,monkeypatch):
    monkeypatch.setattr(campaign_pause,'BASE',tmp_path)
    protected=tmp_path/'protected';protected.mkdir();normal=tmp_path/'normal';normal.mkdir()
    marker=campaign_pause.marker(tmp_path);marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({'schema_version':1,'status':'PAUSED_BY_USER','protected_roots':[str(protected.resolve())],
                                 'logical_task_ids':[]}),encoding='utf-8')
    from jarvis.coder import Coder
    coder=Coder(Mock(),Mock())
    with patch('jarvis.small_program.route',return_value=None),patch('jarvis.engineering_judgment.engine_for',return_value=None),patch.object(coder,'_dispatch',return_value='normal') as dispatch:
        assert coder.run(normal,'ordinary new work')=='normal'
        with pytest.raises(campaign_pause.CampaignPaused):coder.run(protected,'must stay paused')
        assert dispatch.call_count==1
    coder=Coder(SimpleNamespace(base=protected),Mock())
    with pytest.raises(campaign_pause.CampaignPaused):coder.run(normal,'runtime path is protected')
    assert json.loads(marker.read_text(encoding='utf-8'))['status']=='PAUSED_BY_USER'
