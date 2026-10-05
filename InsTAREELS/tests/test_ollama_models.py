import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from jarvis.ollama_models import ALIASES, ALIAS_PARAMETERS, coding_model, model_plan, restore_cached, cached_payload, local_endpoint

ALIAS='jarvis-codex-qwen3.5:9b'
BASE='qwen3.5:9b'


def response(data,status=200):
    result=Mock(status_code=status);result.json.return_value=data
    return result


class OllamaModels(unittest.TestCase):
    def test_missing_coding_model_reports_active_store_without_mutation(self):
        client=Mock();client.post.return_value=response({'error':'model not found'},404)
        client.get.return_value=response({'models':[{'name':'gemma4:e4b'}]})
        with self.assertRaisesRegex(ValueError,'gemma4:e4b.*Windows and WSL'):
            coding_model(client,ALIAS)
        self.assertEqual(client.post.call_count,1)

    def test_missing_alias_rebuilt_from_local_base_before_coding(self):
        client=Mock();client.get.return_value=response({'models':[{'name':BASE}]})
        client.post.side_effect=[response({'error':'not found'},404),response({'status':'success'}),response({'capabilities':['tools']})]
        self.assertEqual(coding_model(client,ALIAS)['capabilities'],['tools'])
        create=client.post.call_args_list[1]
        self.assertTrue(create.args[0].endswith('/api/create'))
        self.assertEqual(create.kwargs['json']['from'],BASE)
        self.assertEqual(create.kwargs['json']['parameters'],ALIAS_PARAMETERS)

    def test_alias_creation_failure_is_not_replayed(self):
        client=Mock();client.get.return_value=response({'models':[{'name':BASE}]})
        client.post.side_effect=[response({},404),response({'status':'unconfirmed'})]
        with self.assertRaisesRegex(ValueError,'not confirmed'):coding_model(client,ALIAS)
        self.assertEqual(client.post.call_count,2)

    def test_registered_model_404_is_endpoint_error_and_tools_are_required(self):
        client=Mock();client.post.return_value=response({},404)
        client.get.return_value=response({'models':[{'name':ALIAS}]})
        with self.assertRaisesRegex(ValueError,'endpoint returned 404'):coding_model(client,ALIAS)
        self.assertEqual(client.post.call_count,1)
        client.post.return_value=response({'capabilities':['completion']})
        with self.assertRaisesRegex(ValueError,'tool support'):coding_model(client,BASE)

    def test_alias_prerequisite_precedes_alias_and_no_remote_endpoint(self):
        plan=model_plan({BASE,ALIAS,'qwen2.5:0.5b'})
        self.assertEqual(plan.count(BASE),1);self.assertLess(plan.index(BASE),plan.index(ALIAS))
        for endpoint in ('https://example.test','http://127.0.0.1:11434/foreign','http://user@localhost:11434','http://localhost:11434?forward=remote'):
            with self.assertRaises(ValueError):local_endpoint(endpoint)

    def fixture(self,root):
        blobs=root/'blobs';blobs.mkdir()
        layers=[]
        for kind,content in [('application/vnd.docker.container.image.v1+json',b'{"renderer":"qwen3.5","parser":"qwen3.5","requires":"0.17.1"}'),
            ('application/vnd.ollama.image.model',b'GGUFchecked-fixture-weights'),
            ('application/vnd.ollama.image.params',b'{"temperature":1}'),
            ('application/vnd.ollama.image.license',b'Original license notice')]:
            digest='sha256:'+hashlib.sha256(content).hexdigest()
            (blobs/digest.replace(':','-')).write_bytes(content)
            layers.append({'mediaType':kind,'digest':digest,'size':len(content)})
        manifest=root/'manifests/registry.ollama.ai/library/qwen3.5/9b';manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'config':layers[0],'layers':layers[1:]}))
        return layers

    def test_cached_restore_streams_checked_weights_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);layers=self.fixture(root);client=Mock()
            client.head.return_value=response({},404)
            client.get.return_value=response({'models':[{'name':BASE}]})
            uploads=[]
            def post(url,**kwargs):
                if '/api/blobs/' in url:
                    content=kwargs['data'].read();self.assertEqual('sha256:'+hashlib.sha256(content).hexdigest(),url.rsplit('/',1)[1]);uploads.append(content)
                    return response({},201)
                payload=kwargs['json'];self.assertEqual(payload['renderer'],'qwen3.5');self.assertEqual(payload['parser'],'qwen3.5')
                self.assertEqual(payload['license'],['Original license notice']);self.assertEqual(payload['parameters'],{'temperature':1})
                return response({'status':'success'})
            client.post.side_effect=post
            self.assertTrue(restore_cached(client,BASE,[root],report=Mock()))
            self.assertEqual(uploads,[b'GGUFchecked-fixture-weights'])
            client.head.return_value=response({},200);uploads.clear()
            self.assertTrue(restore_cached(client,BASE,[root],report=Mock()));self.assertEqual(uploads,[])
            # Corrupted metadata cannot be published or upload any weights.
            (root/'blobs'/layers[-1]['digest'].replace(':','-')).write_bytes(b'X'*layers[-1]['size'])
            client.reset_mock()
            with self.assertRaisesRegex(ValueError,'checksum'):restore_cached(client,BASE,[root],report=Mock())
            client.post.assert_not_called()

    def test_incomplete_cache_is_rejected_and_absent_cache_is_not_downloaded(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.fixture(root)
            client=Mock()
            self.assertFalse(restore_cached(client,'absent:9b',[root],report=Mock()));client.post.assert_not_called()
            (root/'blobs').joinpath(next(p.name for p in (root/'blobs').iterdir() if p.read_bytes().startswith(b'GGUF'))).write_bytes(b'GGUFpartial')
            with self.assertRaisesRegex(ValueError,'incomplete'):cached_payload(root,BASE)
            self.assertIsNone(cached_payload(root,'..:..'))


if __name__=='__main__':unittest.main()
