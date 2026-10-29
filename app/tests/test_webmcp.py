import math
import unittest
from types import SimpleNamespace

from jarvis.webmcp import PageTools, ContractError, bounded_json, checked_schema, origin


class WebMCPContracts(unittest.TestCase):
    def test_disabled_adapter_never_touches_browser(self):
        page=SimpleNamespace(url='https://example.com/')
        adapter=PageTools(page,[])
        self.assertEqual(adapter.discover(),[])
        self.assertIsNone(adapter.select('search'))
        self.assertFalse(adapter.probed)

    def test_schema_limits_reject_references_unknown_keywords_and_depth(self):
        for schema in [{'$ref':'https://outside.invalid/schema'}, {'type':'object','patternProperties':{}},
                       {'type':'object','required':12}]:
            with self.subTest(schema=schema),self.assertRaises(Exception):checked_schema(schema)
        schema={'type':'string'}
        for _ in range(10):schema={'type':'array','items':schema}
        with self.assertRaises(ContractError):checked_schema(schema)

    def test_bounded_json_rejects_nonfinite_oversize_and_cycles(self):
        cycle=[];cycle.append(cycle)
        for value in [math.nan,math.inf,'x'*16001,cycle]:
            with self.subTest(kind=type(value)),self.assertRaises(ContractError):bounded_json(value)
        self.assertEqual(bounded_json({'ok':[True,1,'a']}),{'ok':[True,1,'a']})

    def test_origin_canonicalization_and_secure_transport(self):
        self.assertEqual(origin('https://example.com:443/a'),'https://example.com')
        self.assertEqual(origin('http://127.0.0.1:123/a'),'http://127.0.0.1:123')
        for value in ['http://example.com/','https://user:pass@example.com/','file:///tmp/a']:
            with self.subTest(value=value),self.assertRaises(ContractError):origin(value)

    def test_host_policy_must_pin_all_contract_fields_and_is_copied(self):
        page=SimpleNamespace(url='https://example.com/')
        policy={'origin':'https://example.com','name':'search','operation':'search',
                'inputSchema':{'type':'object'},'outputSchema':{'type':'string'}}
        adapter=PageTools(page,[policy])
        policy['inputSchema']['type']='string'
        self.assertEqual(adapter.policies[('https://example.com','search')]['inputSchema'],{'type':'object'})
        with self.assertRaises(ContractError):PageTools(page,[{**policy,'readOnlyHint':True}])
        with self.assertRaises(ContractError):PageTools(page,[policy,policy])
        with self.assertRaises(ContractError):PageTools(page,[policy],result_encoding='guess')

    def test_cancelled_adapter_skips_probe(self):
        adapter=PageTools(SimpleNamespace(url='https://example.com/'),[],enabled=True,cancelled=lambda:True)
        self.assertEqual(adapter.discover(),[])
        self.assertFalse(adapter.probed)

    def test_discovered_and_selected_offers_cannot_mutate_pinned_dispatch(self):
        page=SimpleNamespace(url='https://example.com/')
        adapter=PageTools(page,[],enabled=True)
        adapter.probed=True
        adapter.handle=SimpleNamespace(evaluate=lambda *args:True)
        adapter.rows=[{'index':0,'name':'search','origin':'https://example.com','operation':'search','untrusted':True}]
        offered=adapter.discover();offered[0]['index']=99
        self.assertEqual(adapter.rows[0]['index'],0)
        selected=adapter.select('search');selected['name']='other_tool'
        self.assertEqual(adapter.rows[0]['name'],'search')


if __name__=='__main__':unittest.main()
