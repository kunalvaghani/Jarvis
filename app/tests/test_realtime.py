import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from jarvis.realtime import Realtime, settings, serious, reader, distance
from jarvis.realtime_catalog import CATALOG, BACKGROUND
from jarvis.realtime_sources import Sources, endpoint, xml_data, MAX_BYTES, countries_key


class Response:
    def __init__(self,data=None,status=200,headers=None,raw=None):
        self.status_code=status; self.headers=headers or {}; self.raw=raw or json.dumps(data or {}).encode()
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def close(self): pass
    def raise_for_status(self):
        if self.status_code>=400:
            import requests
            raise requests.HTTPError(str(self.status_code))
    def iter_content(self,size):
        for start in range(0,len(self.raw),size): yield self.raw[start:start+size]
    def iter_lines(self,**kwargs): return iter(self.raw.splitlines())
    def json(self): return json.loads(self.raw)


NOW=1791350000
LOC={'latitude':22.3,'longitude':73.2,'accuracy':'configured','stale':False}


def record(key,data):
    return {'provider':key,'status':'ok','fetched_at':NOW,'stale':False,'data':data,
        'reference':CATALOG[key].docs,'url':CATALOG[key].url}


class RealtimeTests(unittest.TestCase):
    def service(self,**kwargs):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        options={'enabled':True,'model_enabled':False,'location':LOC}
        options.update(kwargs.pop('options',{}))
        service=Realtime(temp.name,options,Mock(),clock=lambda:NOW,**kwargs)
        self.addCleanup(service.close)
        return service

    def test_exact_green_inventory_and_exclusions(self):
        self.assertEqual(len(CATALOG),82)
        self.assertEqual(len(set(CATALOG)),82)
        for excluded in ('openaq','waqi','nasa_apod','guardian','mastodon','reddit','tavily','brave','coingecko','openf1','youtube','tmdb','fred','geonames','openrouteservice','newsapi'):
            self.assertNotIn(excluded,CATALOG)
        self.assertEqual(set(BACKGROUND),{'weather','air','nws','earthquakes','gdacs','space_weather','eonet'})

    def test_every_adapter_has_bounded_constructible_read(self):
        args={'query':'earth','id':'earth','latitude':22.3,'longitude':73.2,'symbol':'BTC-USD',
              'to_latitude':22.4,'to_longitude':73.3,'country':'IN','timezone':'Asia/Kolkata','route':'bbc/world'}
        ids={'wikidata':'Q42','dictionary':'earth','postcodes':'390001','food':'3017620422003',
             'cover_art':'b84ee12a-09ef-421b-82de-0441a926375b','listenbrainz':'test','coinpaprika':'btc-bitcoin','defillama':'aave'}
        options={'contact':'example@example.com','endpoints':{key:'http://127.0.0.1:9999' for key in ('rsshub','searxng','osrm','opentripplanner','gbfs')}}
        for key,provider in CATALOG.items():
            with self.subTest(key=key):
                specific={**args,'id':ids.get(key,'earth')}
                if key=='nws': specific.update(latitude=38,longitude=-77)
                with patch.dict('os.environ',{'JARVIS_REALTIME_COUNTRIES_KEY':'fixture-free-key'}):
                    url,params,headers,subscription=endpoint(provider,specific,options)
                self.assertTrue(url.startswith(('https://','http://','wss://')))
                self.assertTrue(provider.docs.startswith(('https://','http://')))
                self.assertLess(len(json.dumps(params)),2000)

    def test_configuration_rejects_models_and_invalid_limits(self):
        for raw in ({'enabled':'yes'},{'model':'qwen3.5:9b'},{'min_available_mb':1},
            {'endpoints':{'reddit':'https://example.com'}},{'contact':'bad\nheader'},
            {'location':{'latitude':float('nan'),'longitude':1}}):
            with self.subTest(raw=raw),self.assertRaises((ValueError,TypeError)): settings(raw)

    def test_http_cache_and_same_provider_cadence(self):
        http=Mock(); http.get.return_value=Response({'value':4})
        source=Sources(transport=http,clock=lambda:NOW)
        first=source.fetch('crossref',{'query':'test'})
        cached=source.fetch('crossref',{'query':'test'})
        other=source.fetch('crossref',{'query':'different'})
        self.assertEqual(first['status'],'ok'); self.assertTrue(cached['cached'])
        self.assertEqual(other['status'],'rate_limited'); self.assertEqual(http.get.call_count,1)
        self.assertFalse(http.get.call_args.kwargs['allow_redirects'])

    def test_429_reserves_backoff_and_never_retries_write(self):
        http=Mock(); http.get.return_value=Response(status=429,headers={'Retry-After':'1200'})
        source=Sources(transport=http,clock=lambda:NOW)
        self.assertEqual(source.fetch('crossref',{'query':'x'})['status'],'unavailable')
        self.assertGreaterEqual(source.next['crossref'],NOW+1200)
        self.assertEqual(source.fetch('crossref',{'query':'y'})['status'],'rate_limited')
        self.assertEqual(http.get.call_count,1)

    def test_oversized_json_is_rejected(self):
        http=Mock(); http.get.return_value=Response(raw=b' '*(MAX_BYTES+1))
        row=Sources(transport=http,clock=lambda:NOW).fetch('bbc')
        self.assertNotEqual(row['status'],'ok'); self.assertTrue(row['stale'])

    def test_provider_exception_does_not_publish_private_urls_or_keys(self):
        import requests
        http = Mock()
        http.get.side_effect = requests.ConnectionError('https://private.example/private-token/feed?api-key=fixture-secret')
        source = Sources({'endpoints': {'gbfs': 'https://private.example/private-token/feed?api-key=fixture-secret'}}, transport=http)
        row = source.fetch('gbfs')
        self.assertEqual(row['status'], 'unavailable')
        self.assertNotIn('fixture-secret', json.dumps(row))
        self.assertNotIn('private-token', json.dumps(row))

    def test_configured_feed_receipts_omit_query_and_private_path(self):
        http = Mock(); http.get.return_value = Response({'stations': []})
        row = Sources({'endpoints': {'gbfs': 'https://private.example/private-token/feed?key=fixture-secret'}}, transport=http).fetch('gbfs')
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['url'], 'https://private.example')
        self.assertNotIn('fixture-secret', json.dumps(row))
        self.assertNotIn('private-token', json.dumps(row))

    def test_retry_after_http_date_and_malformed_values_preserve_backoff(self):
        from datetime import datetime, timezone
        from email.utils import format_datetime
        for value, delay in [(format_datetime(datetime.fromtimestamp(NOW+1200, timezone.utc), usegmt=True), 1200),
                             ('invalid', 300), ('NaN', 300), ('-1', CATALOG['crossref'].interval)]:
            with self.subTest(value=value):
                http = Mock(); http.get.return_value = Response(status=429, headers={'Retry-After': value})
                source = Sources(transport=http, clock=lambda: NOW)
                self.assertEqual(source.fetch('crossref', {'query': 'x'})['status'], 'unavailable')
                self.assertEqual(source.next['crossref'], NOW+delay)
                self.assertEqual(http.get.call_count, 1)

    def test_ignored_countries_key_loading_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'JARVIS_REALTIME_COUNTRIES_KEY': ''}):
            path = Path(directory) / 'secrets/realtime.json'
            path.parent.mkdir()
            path.write_text(json.dumps({'countries_api_key': 'fixture-local'}))
            self.assertEqual(countries_key(directory), 'fixture-local')
            with patch.dict('os.environ', {'JARVIS_REALTIME_COUNTRIES_KEY': 'fixture-env'}):
                self.assertEqual(countries_key(directory), 'fixture-env')
            path.write_text('{broken fixture-secret')
            with self.assertRaises(ValueError) as caught:
                countries_key(directory)
            self.assertNotIn('fixture-secret', str(caught.exception))
            path.write_text(json.dumps({'countries_api_key': 'bad\nheader'}))
            with self.assertRaises(ValueError): countries_key(directory)

    def test_countries_v5_uses_property_query_and_objects_envelope(self):
        http = Mock(); http.get.return_value = Response({'data': {'objects': [{'names': {'common': 'India'}}]}})
        with patch.dict('os.environ', {'JARVIS_REALTIME_COUNTRIES_KEY': 'fixture-key'}):
            row = Sources(transport=http).fetch('countries', {'id': 'India'})
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['data'][0]['names']['common'], 'India')
        self.assertEqual(http.get.call_args.args[0], 'https://api.restcountries.com/countries/v5/names.common')
        self.assertEqual(http.get.call_args.kwargs['params'], {'q': 'India', 'limit': 5})
        self.assertNotIn('fixture-key', json.dumps(row))

    def test_cancel_during_read_does_not_publish_data(self):
        stop=threading.Event()
        response=Response({'test':1})
        def chunks(size):
            stop.set(); yield response.raw
        response.iter_content=chunks
        http=Mock(); http.get.return_value=response
        source=Sources(transport=http,clock=lambda:NOW)
        row=source.fetch('crossref',{},stop.is_set)
        self.assertNotEqual(row['status'],'ok'); self.assertFalse(source.cache)

    def test_cached_failure_is_marked_stale(self):
        now=[NOW]; http=Mock(); http.get.side_effect=[Response({'value':4}),Response(status=503)]
        source=Sources(transport=http,clock=lambda:now[0])
        source.fetch('crossref',{})
        now[0]+=100
        row=source.fetch('crossref',{})
        self.assertTrue(row['stale']); self.assertEqual(row['data']['value'],4)
        self.assertEqual(row['fetched_at'],NOW)

    def test_selfhost_and_contact_requirements_no_public_substitution(self):
        http=Mock(); source=Sources(transport=http,clock=lambda:NOW)
        for key in ('searxng','rsshub','opentripplanner','gbfs','met','musicbrainz'):  # OSRM has a public default.
            with self.subTest(key=key): self.assertEqual(source.fetch(key)['status'],'needs_configuration')
        http.get.assert_not_called()

    def test_xml_entities_and_atom_feed(self):
        with self.assertRaises(ValueError): xml_data(b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///x">]><x/>')
        data=xml_data(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>New paper</title><link href="https://arxiv.org/abs/x"/></entry></feed>')
        self.assertEqual(data['items'][0]['title'],'New paper')
        self.assertTrue(data['items'][0]['link'].startswith('https://'))

    def test_sse_sample_has_no_resident_stream(self):
        http=Mock(); http.get.return_value=Response(raw=b'data: {"id":1}\n\ndata: {"id":2}\n\ndata: {"id":3}\n')
        row=Sources(transport=http,clock=lambda:NOW).fetch('wikimedia_events')
        self.assertTrue(row['sample']); self.assertEqual(len(row['data']['events']),3)

    def test_websocket_ack_not_ticker(self):
        connection=Mock(); connection.recv.side_effect=[json.dumps({'type':'subscriptions'}),json.dumps({'type':'ticker','price':'100'})]*3
        with patch('websocket.create_connection',return_value=connection):
            row=Sources(clock=lambda:NOW).fetch('coinbase_stream',{'symbol':'BTC-USD'})
        self.assertEqual(row['status'],'ok'); self.assertEqual(row['data']['events'][0]['type'],'ticker')
        connection.close.assert_called_once()
        self.assertEqual(json.loads(connection.send.call_args.args[0])['channels'],['ticker'])

    def test_coordinate_validation_and_no_arbitrary_url(self):
        source=Sources(transport=Mock(),clock=lambda:NOW)
        with self.assertRaises(ValueError): source.fetch('https://example.com')
        self.assertEqual(source.fetch('weather',{'latitude':100,'longitude':0})['status'],'needs_configuration')
        with self.assertRaises(ValueError): endpoint(CATALOG['coinbase'],{'symbol':'../secrets'}, {})

    def test_canonical_feed_redirect_and_arbitrary_target_denial(self):
        http=Mock(); http.get.side_effect=[Response(status=302,headers={'Location':'https://news.google.com/rss/search?q=test&hl=en-IN'}),Response(raw=b'<rss><channel><item><title>News</title></item></channel></rss>')]
        result=Sources(transport=http,clock=lambda:NOW).fetch('google_news',{'query':'test'})
        self.assertEqual(result['status'],'ok'); self.assertEqual(http.get.call_count,2)
        http=Mock(); http.get.return_value=Response(status=302,headers={'Location':'http://127.0.0.1/private'})
        result=Sources(transport=http,clock=lambda:NOW).fetch('google_news',{'query':'test'})
        self.assertEqual(result['status'],'unavailable'); self.assertEqual(http.get.call_count,1)

    def test_malformed_provider_data_is_not_a_configuration_error(self):
        http=Mock(); http.get.return_value=Response(raw=b'not json')
        self.assertEqual(Sources(transport=http,clock=lambda:NOW).fetch('crossref')['status'],'unavailable')

    def test_null_model_weather_values_do_not_raise_or_alert(self):
        for key,current in [('weather',{'wind_speed_10m':None,'temperature_2m':None}),('air',{'us_aqi':None})]:
            self.assertFalse(serious(record(key,{'current':{'time':datetime_text(NOW),**current}}),LOC,NOW))

    def test_nws_outside_us_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'US territories'): endpoint(CATALOG['nws'],LOC,{})

    def test_location_never_uses_weather_fallback_city(self):
        service=self.service(options={'location':None,'auto_location':False})
        self.assertEqual(service.query('weather')['status'],'location_required')

    def test_ip_location_is_approximate_and_refreshable(self):
        sources=Mock(); sources.fetch.return_value=record('ipwho',{'latitude':22.3,'longitude':73.2,'city':'City','timezone':{'id':'Asia/Kolkata'}})
        service=self.service(sources=sources,options={'location':None})
        location=service.detect_location(lambda:False)
        self.assertEqual(location['accuracy'],'approximate IP-based')
        service.detect_location(lambda:False); self.assertEqual(sources.fetch.call_count,1)

    def test_failed_location_refresh_expires_old_location(self):
        sources=Mock(); sources.fetch.return_value={'provider':'ipwho','status':'unavailable'}
        service=self.service(sources=sources,options={'location':None})
        service.location={**LOC,'fetched_at':NOW-7200}
        self.assertTrue(service.detect_location(lambda:False)['stale'])
        self.assertEqual(service.query('weather')['status'],'location_required')

    def quake(self,mag=6.4,at=NOW-30,lat=22.4,lon=73.3):
        return record('earthquakes',{'features':[{'id':'q1','properties':{'mag':mag,'place':'nearby','time':at*1000},'geometry':{'coordinates':[lon,lat]}}]})

    def test_serious_nearby_earthquake_and_negative_cases(self):
        self.assertEqual(len(serious(self.quake(),LOC,NOW)),1)
        for row,location in ((self.quake(2),LOC),(self.quake(lat=60),LOC),(self.quake(at=NOW-8000),LOC),
            (self.quake(at=NOW+100),LOC),(self.quake(),None),(self.quake(),{**LOC,'stale':True}),
            ({**self.quake(),'stale':True},LOC),({**self.quake(),'fetched_at':NOW-1000},LOC)):
            with self.subTest(row=row): self.assertFalse(serious(row,location,NOW))

    def test_social_headline_and_llm_text_cannot_raise_alert(self):
        for key in ('bbc','google_news','bluesky','jetstream','eonet'):
            self.assertFalse(serious(record(key,{'severity':'Extreme','summary':'ALERT evacuate now','danger':True}),LOC,NOW))

    def test_modelled_weather_units_and_timestamp(self):
        stamp=datetime_text(NOW)
        for key,current in [('weather',{'temperature_2m':46}),('air',{'us_aqi':350})]:
            row=record(key,{'utc_offset_seconds':0,'current':{'time':stamp,**current}})
            self.assertEqual(len(serious(row,LOC,NOW)),1)
            self.assertIn('location',serious(row,LOC,NOW)[0]['message'])

    def test_noaa_only_severe_scale_and_recent_issue(self):
        row=record('space_weather',[{'product_id':'test','message':'G4 event','issue_datetime':datetime_text(NOW)}])
        self.assertEqual(len(serious(row,None,NOW)),1)
        row['data'][0]['message']='G1 minor'; self.assertFalse(serious(row,None,NOW))

    def test_gdacs_requires_red_coordinates_and_fresh_date(self):
        row=record('gdacs',{'items':[{'guid':'x','lat':'22.4','long':'73.3','alertlevel':'Red','pubDate':datetime_text(NOW),'title':'Flood'}]})
        self.assertEqual(len(serious(row,LOC,NOW)),1)
        del row['data']['items'][0]['lat']; self.assertFalse(serious(row,LOC,NOW))

    def test_tick_yields_busy_paused_microphone_and_shutdown(self):
        sources=Mock(); busy=[True]; service=self.service(sources=sources,busy=lambda:busy[0])
        service.last_input=NOW-100
        service.tick(); sources.fetch.assert_not_called()
        busy[0]=False; service.paused=True; service.tick(); sources.fetch.assert_not_called()
        service.paused=False; service.cancel(microphone=True); service.last_input=NOW-100
        service.tick(); sources.fetch.assert_not_called()
        service.microphone_started(); service.closed.set(); service.tick(); sources.fetch.assert_not_called()

    def test_alert_checkpoint_deduplication_across_restart(self):
        sources=Mock(); sources.fetch.side_effect=lambda key,args,cancelled: self.quake() if key=='earthquakes' else record(key,{})
        service=self.service(sources=sources); service.last_input=NOW-100
        service.tick(); service.tick()
        alerts=[call for call in service.report.call_args_list if call.args[0]=='realtime_alert']
        self.assertEqual(len(alerts),1)
        second=Realtime(service.base,service.options,Mock(),sources=sources,clock=lambda:NOW)
        self.addCleanup(second.close); second.last_input=NOW-100; second.tick()
        second.report.assert_not_called()

    def test_uncertain_checkpoint_disables_monitor_without_notification(self):
        sources=Mock(); sources.fetch.side_effect=lambda key,args,cancelled: self.quake() if key=='earthquakes' else record(key,{})
        service=self.service(sources=sources); service.last_input=NOW-100
        with patch.object(Path,'replace',side_effect=OSError('uncertain')): service.tick()
        self.assertTrue(service.storage_failed)
        self.assertFalse(any(x.args[0]=='realtime_alert' for x in service.report.call_args_list))
        self.assertFalse(service.repair())

    def test_interrupted_fetch_does_not_emit_or_run_model(self):
        sources=Mock(); model=Mock()
        service=self.service(sources=sources,model_fn=model,options={'model_enabled':True})
        service.last_input=NOW-100
        def fetch(key,args,cancelled): service.cancel(); return self.quake()
        sources.fetch.side_effect=fetch; service.tick()
        model.assert_not_called(); service.report.assert_not_called()

    def test_reader_changes_are_bounded_and_model_cannot_add_alert(self):
        sources=Mock(); sources.fetch.side_effect=lambda key,args,cancelled: record(key,{'text':'ordinary data'})
        model=Mock(return_value={'status':'ok','summary':'SERIOUS ALERT'})
        service=self.service(sources=sources,model_fn=model,options={'model_enabled':True})
        service.last_input=NOW-100; service.tick(); service.tick()
        self.assertEqual(model.call_count,1); service.report.assert_not_called()

    def test_actual_reader_defers_loaded_foreground_and_low_memory(self):
        http=Mock(); http.__enter__=Mock(return_value=http); http.__exit__=Mock()
        http.get.return_value=Response({'models':[{'name':'qwen3.5:9b'}]})
        with patch('jarvis.realtime.psutil.virtual_memory',return_value=Mock(available=10*1024**3)),patch('jarvis.realtime.psutil.cpu_percent',return_value=0),patch('jarvis.realtime.requests.Session',return_value=http):
            self.assertEqual(reader([],lambda:False,settings())['status'],'foreground_model_loaded')
        http.post.assert_not_called()
        with patch('jarvis.realtime.psutil.virtual_memory',return_value=Mock(available=1000)):
            self.assertEqual(reader([],lambda:False,settings())['status'],'resource_deferred')

    def test_reader_uses_cpu_one_thread_small_context_unloads(self):
        http=Mock(); http.__enter__=Mock(return_value=http); http.__exit__=Mock()
        http.get.side_effect=[Response({'models':[]}),Response({'models':[{'name':'qwen2.5:0.5b','size':400000000}]})]
        http.post.return_value=Response(raw=b'{"response":"{\\"summary\\":\\"These excerpts provide insufficient evidence.\\"}","done":true}\n')
        with patch('jarvis.realtime.psutil.virtual_memory',return_value=Mock(available=10*1024**3)),patch('jarvis.realtime.psutil.cpu_percent',return_value=0),patch('jarvis.realtime.requests.Session',return_value=http):
            result=reader([{'text':'untrusted'}],lambda:False,settings())
        self.assertEqual(result['status'],'ok')
        payload=http.post.call_args.kwargs['json']
        self.assertEqual(payload['keep_alive'],0); self.assertEqual(payload['options']['num_thread'],1)
        self.assertEqual(payload['options']['num_gpu'],0); self.assertEqual(payload['options']['num_ctx'],1024)
        self.assertLessEqual(len(payload['prompt']),1500)

    def test_relevant_selection_operand_and_question_evidence(self):
        sources=Mock(); sources.fetch.return_value=record('dictionary',{'word':'earth'})
        service=self.service(sources=sources)
        context=service.context('Free Dictionary API: earth')
        self.assertEqual(sources.fetch.call_args.args[1]['id'],'earth')
        self.assertEqual(context['sources'][0]['provider'],'dictionary')
        self.assertIsNone(service.context('Open Notepad'))
        self.assertEqual(service.selection('Open-Meteo Air Quality'),['air'])

    def test_ambiguous_requested_city_does_not_guess_location(self):
        sources=Mock(); sources.fetch.return_value=record('geocoding',{'results':[{'name':'Paris'},{'name':'Paris'}]})
        service=self.service(sources=sources)
        context=service.context('weather in Paris')
        self.assertTrue(context['location_required']); self.assertEqual(sources.fetch.call_count,1)

    def test_controls_stop_resume_and_manual_session_location(self):
        service=self.service()
        service.controls('pause realtime'); self.assertTrue(service.paused)
        service.controls('resume realtime'); self.assertFalse(service.paused)
        service.controls('set realtime location 40.7, -74.0'); self.assertEqual(service.location['latitude'],40.7)
        service.controls('use current realtime location'); self.assertIsNone(service.location)

    def test_tool_query_boundary_and_answer_evidence(self):
        from jarvis.tools import ToolRegistry
        actions=Mock(); actions.realtime.query.return_value=record('crossref',{'title':'Paper'})
        result=ToolRegistry(actions)._execute({'action':'realtime_query','value':'crossref','content':'{"query":"earth"}'},lambda:False)
        self.assertEqual(json.loads(result.evidence)['status'],'ok')
        actions.realtime.query.assert_called_once()
        from jarvis.knowledge_worker import answer
        chat=Mock(return_value=json.dumps({'answer':'From Crossref.','needs_web':False})); search=Mock()
        response=answer({'question':'research papers today','realtime_context':{'sources':[record('crossref',{'title':'Paper'})]},'options':{'answer_language':'en'}},chat_fn=chat,search_fn=search)
        self.assertEqual(response['answer'],'From Crossref.'); search.assert_not_called()
        self.assertIn('untrusted data',chat.call_args.args[2][0]['content'])
        self.assertIn('Respond only in English',chat.call_args.args[2][0]['content'])

    def test_service_health_recovery_and_deliberate_close(self):
        service=self.service(); service.start(); self.assertTrue(service.healthy())
        service.close(); self.assertFalse(service.repair())

    def test_model_setup_declares_small_reader_without_larger_fallback(self):
        from jarvis.model_selection import required_models
        self.assertIn('qwen2.5:0.5b',required_models({'realtime':{'enabled':True}}))
        self.assertNotIn('qwen2.5:0.5b',required_models({'realtime':{'enabled':False}}))

    def test_reader_failure_does_not_suppress_confirmed_hazard(self):
        sources=Mock(); sources.fetch.side_effect=lambda key,args,cancelled: self.quake() if key=='earthquakes' else record(key,{})
        service=self.service(sources=sources,model_fn=Mock(side_effect=TimeoutError()),options={'model_enabled':True})
        service.last_input=NOW-100; service.tick()
        self.assertEqual(service.summary['status'],'reader_unavailable')
        self.assertEqual(sum(call.args[0]=='realtime_alert' for call in service.report.call_args_list),1)

    def test_malformed_hazard_data_is_silent(self):
        for key,data in [('earthquakes',{'features':[None]}),('air',{'current':None}),('space_weather',['G5'])]:
            self.assertEqual(serious(record(key,data),LOC,NOW),[])

    def test_explicit_question_coordinates_are_not_ip_location(self):
        sources=Mock(); sources.fetch.return_value=record('weather',{'current':{}})
        service=self.service(sources=sources)
        context=service.context('weather at 40.7, -74.0')
        self.assertEqual(sources.fetch.call_args.args[1]['latitude'],40.7)
        self.assertEqual(context['sources'][0]['location']['accuracy'],'request coordinates')

    def test_country_disambiguates_requested_city(self):
        sources=Mock(); sources.fetch.side_effect=[record('geocoding',{'results':[{'name':'Paris','country':'France','latitude':48.8,'longitude':2.3},{'name':'Paris','country':'USA','latitude':33,'longitude':-95}]}),record('weather',{'current':{}})]
        service=self.service(sources=sources)
        context=service.context('weather in Paris, France')
        self.assertFalse(context.get('location_required',False)); self.assertEqual(sources.fetch.call_args.args[1]['latitude'],48.8)

    def test_configured_timezone_does_not_guess_a_home_timezone(self):
        service=self.service()
        self.assertEqual(service.query('timeapi')['status'],'timezone_required')

    def test_loopback_selfhost_services_use_read_only_adapter_contracts(self):
        http=Mock(); http.get.return_value=Response({'result':'local fixture only'})
        source=Sources({'endpoints':{'searxng':'http://127.0.0.1:9999','osrm':'http://127.0.0.1:9999','opentripplanner':'http://127.0.0.1:9999','rsshub':'http://127.0.0.1:9999','gbfs':'http://127.0.0.1:9999'}},transport=http,clock=lambda:NOW)
        self.assertEqual(source.fetch('searxng',{'query':'test'})['status'],'ok')
        self.assertIn('/search',http.get.call_args.args[0])
        self.assertEqual(source.fetch('osrm',{**LOC,'to_latitude':22.4,'to_longitude':73.3})['status'],'ok')
        self.assertIn('/route/v1/driving/',http.get.call_args.args[0])
        self.assertEqual(source.fetch('opentripplanner',{**LOC,'to_latitude':22.4,'to_longitude':73.3})['status'],'ok')
        self.assertIn('/otp/routers/default/plan',http.get.call_args.args[0])

    def test_country_free_key_is_explicit_and_never_in_url_or_receipt(self):
        http=Mock(); http.get.return_value=Response({'data':{'objects':[{'names':{'common':'India'}}]}})
        keyless=Mock(); keyless.get.return_value=Response([{'page':1},[{'id':'IND','iso2Code':'IN','name':'India','capitalCity':'New Delhi'},
                                                                     {'id':'USA','iso2Code':'US','name':'United States'}]])
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{},clear=True):
            source=Sources(transport=keyless,clock=lambda:NOW,credential_base=directory)
            row=source.fetch('countries',{'id':'India'})
            self.assertEqual(row['status'],'ok'); self.assertEqual(row['data'][0]['capitalCity'],'New Delhi')
            self.assertEqual(keyless.get.call_args.args[0],'https://api.worldbank.org/v2/country')
            self.assertNotIn('Authorization',keyless.get.call_args.kwargs['headers'])
        with patch.dict('os.environ',{'JARVIS_REALTIME_COUNTRIES_KEY':'fixture-secret'}):
            source=Sources(transport=http,clock=lambda:NOW)
            row=source.fetch('countries',{'id':'India'})
        self.assertEqual(row['status'],'ok'); self.assertNotIn('fixture-secret',json.dumps(row))
        self.assertEqual(http.get.call_args.kwargs['headers']['Authorization'],'Bearer fixture-secret')

    def test_old_task_context_is_marked_stale_and_never_sends_goal(self):
        service=self.service(sources=Mock())
        service.rows['weather']={**record('weather',{'current':{}}),'fetched_at':NOW-1000}
        context=service.context('Build a weather app in private project directory',refresh=False)
        self.assertTrue(context['sources'][0]['stale']); service.sources.fetch.assert_not_called()

    def test_cancelled_websocket_closes_connection_and_emits_no_observation(self):
        connection=Mock(); closed=threading.Event()
        def recv(): closed.set(); return json.dumps({'type':'ticker','price':'100'})
        connection.recv.side_effect=recv
        with patch('websocket.create_connection',return_value=connection):
            row=Sources(clock=lambda:NOW).fetch('coinbase_stream',{},closed.is_set)
        self.assertEqual(row['status'],'cancelled'); connection.close.assert_called_once()

    def test_gdacs_nested_geometry_retains_latitude_and_longitude(self):
        data=xml_data(b'<rss xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#"><channel><item><title>Flood</title><geo:Point><geo:lat>22.4</geo:lat><geo:long>73.3</geo:long></geo:Point></item></channel></rss>')
        self.assertEqual(data['items'][0]['lat'],'22.4'); self.assertEqual(data['items'][0]['long'],'73.3')

    def test_voice_control_parser_and_final_only_engine_routing(self):
        from jarvis.commands import parse
        from jarvis.engine import Engine
        for value in ('realtime status','pause realtime','resume realtime','stop realtime alerts',
            'set realtime location 22.3, 73.2','use current realtime location'):
            with self.subTest(value=value): self.assertEqual(parse(value).kind,'realtime')
        sent=[]; engine=Engine(sent.append,Mock()); engine.activate()
        engine.feed('pause realtime',final=False); self.assertFalse(sent)
        engine.feed('pause realtime',final=True); self.assertEqual(sent[0].kind,'realtime')

    def test_actions_controls_bypass_question_and_mutation_queues(self):
        from jarvis.actions import Actions
        from jarvis.commands import parse
        with tempfile.TemporaryDirectory() as directory:
            actions=Actions({'files_root':'files','apps':{},'realtime':{'enabled':False}},directory,Mock())
            try:
                actions.knowledge.submit=Mock()
                actions.submit(parse('realtime status')); actions.submit(parse('pause realtime'))
                self.assertTrue(actions.realtime.paused); self.assertTrue(actions.queue.empty())
                actions.knowledge.submit.assert_not_called()
            finally: actions.close()


def datetime_text(value):
    from datetime import datetime,timezone
    return datetime.fromtimestamp(value,timezone.utc).isoformat()


if __name__=='__main__': unittest.main()
