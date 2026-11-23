"""Public catalog adapter fixtures; no downloaded model or autonomous case proof."""
import hashlib,json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from jarvis.discovery.adapters import asset_catalog
from jarvis.discovery.asset_search import adapters,NODES
from jarvis.neural.service import BrainService

RAW=json.dumps({'results':[{'uid':'a'*32,'name':'Unverified model label','isDownloadable':True,
    'viewerUrl':'https://sketchfab.com/3d-models/example','user':{'username':'creator'},
    'license':{'label':'CC BY','url':'https://creativecommons.org/licenses/by/4.0/'}}]}).encode()


def test_public_search_retains_actual_bytes_but_never_promotes_asset(tmp_path):
    calls=[]
    def fetch(url):calls.append(url);return RAW
    result=asset_catalog.search(tmp_path,'cube model',fetch)
    assert len(calls)==1 and calls[0].startswith('https://api.sketchfab.com/v3/search?')
    assert (tmp_path/result['cached_metadata']).read_bytes()==RAW
    assert result['payload_sha256']==hashlib.sha256(RAW).hexdigest()
    assert result['download_authentication_required'] and not result['binary_download_performed']
    assert not result['items'][0]['identity_verified'] and not result['items'][0]['geometry_acquired']
    assert result['items'][0]['engineering_suitability']=='UNASSESSED'


def test_cached_bytes_cannot_be_silently_overwritten(tmp_path):
    result=asset_catalog.search(tmp_path,'cube model',lambda _:RAW)
    (tmp_path/result['cached_metadata']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='cache changed'):asset_catalog.search(tmp_path,'cube model',lambda _:RAW)


@pytest.mark.parametrize('url',['https://127.0.0.1/private','http://api.sketchfab.com/v3/search',
    'https://example.org/steal','https://user:pass@api.sketchfab.com/v3/search'])
def test_redirects_cannot_leave_public_api_or_add_credentials(url):
    with pytest.raises(ValueError):asset_catalog.SameOrigin().redirect_request(None,None,302,'',{},url)


def test_missing_or_malformed_metadata_is_not_success(tmp_path):
    for raw in (b'{}',b'not JSON',b'x'*(asset_catalog.CAP+1)):
        with pytest.raises(ValueError):asset_catalog.search(tmp_path,'cube model',lambda _:raw)


def test_detail_preserves_concept_description_and_requires_matching_uid(tmp_path):
    row=json.loads(RAW)['results'][0];row['description']='A creator concept; not official engineering geometry.'
    detail=asset_catalog.detail(tmp_path,'a'*32,lambda _:json.dumps(row).encode())
    assert detail['lookup_mode']=='detail'
    assert 'creator concept' in detail['items'][0]['description']
    assert not detail['items'][0]['identity_verified']
    with pytest.raises(ValueError,match='identity differs'):
        asset_catalog.detail(tmp_path,'b'*32,lambda _:json.dumps(row).encode())


def test_real_source_handler_and_verifier_reject_changed_local_cache(tmp_path):
    config={'lab':{'enabled':True,'research':True,'sim':True},'neural':{'mode':'act'}}
    service=BrainService(config,tmp_path/'brain.sqlite3')
    try:
        env=SimpleNamespace(actions=SimpleNamespace(base=tmp_path,config=config,report=lambda *a:None),cancelled=lambda:False)
        handlers=adapters(service.graph,service.journal)
        real=asset_catalog.search
        with patch.object(asset_catalog,'search',side_effect=lambda base,q:real(base,q,lambda _:RAW)):
            public=handlers[NODES['run']](None,{'request':{'query':'cube model'}},env)
        args={'request':{'query':'cube model'},'report':public['report']}
        assert handlers[NODES['check']](None,args,env)['verdict']['passed']
        path=tmp_path/public['report']['result']['cached_metadata'];path.write_bytes(b'{}')
        assert not handlers[NODES['check']](None,args,env)['verdict']['passed']
    finally:service.journal.close()
