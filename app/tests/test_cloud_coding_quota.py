"""Network-free project/model quota simulations; no provider inference."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from dateutil.tz import gettz
from jarvis.cloud_quota import CloudQuotaManager, QuotaDenied
from jarvis.coding_cloud_policy import gemini_settings, gemini_eligible


class CloudCodingQuota(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'quota.sqlite3'
        self.now=datetime(2026,10,29,12,tzinfo=timezone.utc).timestamp()
        self.options={**gemini_settings(),'provider':'gemini','keep_dispatch_time':True}
        self.guard=CloudQuotaManager(self.path,self.options,clock=lambda:self.now)

    def request(self,**kwargs):
        identifier=self.guard.reserve(self.options['model'],110,input_tokens=100,output_tokens=10,**kwargs)
        self.guard.finish(identifier,{'prompt_tokens':50,'completion_tokens':5,'total_tokens':55})
        return identifier

    def test_all_sixteen_daily_calls_and_seventeenth_denied_without_daily_token_limit(self):
        for index in range(16):
            if index and index%4==0:self.now+=61
            self.request()
        snapshot=self.guard.snapshot(fresh=True)
        self.assertEqual(snapshot['remaining']['daily_requests'],0)
        self.assertNotIn('daily_tokens',snapshot['remaining'])
        self.assertNotIn('minute_tokens',snapshot['remaining'])
        with self.assertRaisesRegex(QuotaDenied,'daily_requests'):self.request()

    def test_four_minute_calls_and_fifth_denied_then_minute_recovers(self):
        for _ in range(4):self.request()
        with self.assertRaisesRegex(QuotaDenied,'minute_requests'):self.request()
        self.now+=61;self.request()
        self.assertEqual(self.guard.snapshot(fresh=True)['used']['daily_requests'],5)

    def test_input_token_dimension_is_distinct_from_combined_or_daily_tokens(self):
        identifier=self.guard.reserve(self.options['model'],200001,input_tokens=200000,output_tokens=1)
        self.guard.finish(identifier,{'prompt_tokens':200000,'completion_tokens':1,'total_tokens':200001})
        with self.assertRaisesRegex(QuotaDenied,'minute_input_tokens'):self.request()
        self.now+=61;self.request()
        self.assertEqual(self.guard.snapshot(fresh=True)['used']['daily_tokens'],200056)

    def test_midnight_pacific_spring_and_autumn_boundaries(self):
        zone=gettz('America/Los_Angeles')
        for month,day in [(3,8),(11,1),(10,29)]:
            with self.subTest(month=month):
                self.path=Path(self.temp.name)/('day-'+str(month)+'.sqlite3')
                self.now=datetime(2026,month,day,23,59,50,tzinfo=zone).timestamp()
                self.guard=CloudQuotaManager(self.path,self.options,clock=lambda:self.now)
                self.request();before=self.guard.snapshot(fresh=True)
                self.assertEqual(before['used']['daily_requests'],1)
                self.now+=11;after=self.guard.snapshot(fresh=True)
                self.assertEqual(after['used']['daily_requests'],0)
                self.assertEqual(after['used']['minute_requests'],1)
                self.assertEqual(datetime.fromtimestamp(after['daily_reset_at'],zone).hour,0)
                self.assertEqual(before['daily_reset_at'],self.now-1)

    def test_day_duration_uses_dst_rules_not_fixed_twenty_four_hours(self):
        zone=gettz('America/Los_Angeles')
        for month,day,hours in [(3,8,23),(11,1,25)]:
            self.now=datetime(2026,month,day,0,0,tzinfo=zone).timestamp()
            self.guard=CloudQuotaManager(Path(self.temp.name)/str(month),self.options,clock=lambda:self.now)
            self.assertEqual(self.guard.snapshot(fresh=True)['daily_reset_at']-self.now,hours*3600)

    def test_restart_crash_uncertain_and_concurrent_reservations_are_conservative(self):
        identifier=self.guard.reserve(self.options['model'],100,input_tokens=90,output_tokens=10)
        other=CloudQuotaManager(self.path,self.options,clock=lambda:self.now)
        self.assertEqual(other.snapshot(fresh=True)['used']['daily_requests'],1)
        with self.assertRaisesRegex(QuotaDenied,'concurrent'):other.reserve(self.options['model'],10)
        self.guard.finish(identifier)
        self.assertEqual(other.snapshot(fresh=True)['used']['daily_tokens'],100)
        def reserve(_):
            try:return CloudQuotaManager(self.path,self.options,clock=lambda:self.now).reserve(self.options['model'],10)
            except QuotaDenied:return None
        with ThreadPoolExecutor(max_workers=5) as pool:values=list(pool.map(reserve,range(5)))
        self.assertEqual(sum(bool(value) for value in values),1)

    def test_task_call_cap_survives_restart_and_minute_reset(self):
        task='a'*32
        for _ in range(3):self.request(task_id=task,task_limit=3)
        self.now+=61;self.guard=CloudQuotaManager(self.path,self.options,clock=lambda:self.now)
        with self.assertRaisesRegex(QuotaDenied,'task_call_limit'):self.request(task_id=task,task_limit=3)
        self.request(task_id='b'*32,task_limit=3)

    def test_external_lower_limits_remaining_and_429_backoff_survive_restart(self):
        self.request();self.guard.feedback('daily_requests',limit=10,remaining=2,reset_at=self.now+3600)
        self.assertEqual(self.guard.snapshot(fresh=True)['remaining']['daily_requests'],0)  # provider headroom is retained despite external usage
        self.guard.block(60);self.guard=CloudQuotaManager(self.path,self.options,clock=lambda:self.now)
        with self.assertRaisesRegex(QuotaDenied,'provider_backoff'):self.request()
        self.now+=3601;self.guard.confirm_clock(self.now)  # simulated provider metadata after the earlier daily feedback expires
        self.guard.feedback('minute_input_tokens',limit=100)
        with self.assertRaisesRegex(QuotaDenied,'minute_input_tokens'):self.request()

    def test_completed_request_remains_in_dispatch_day_when_completion_crosses_midnight(self):
        zone=gettz('America/Los_Angeles');self.now=datetime(2026,10,29,23,59,59,tzinfo=zone).timestamp()
        self.guard=CloudQuotaManager(self.path,self.options,clock=lambda:self.now)
        identifier=self.guard.reserve(self.options['model'],100)
        self.now+=2;self.guard.finish(identifier,{'total_tokens':80})
        self.assertEqual(self.guard.snapshot(fresh=True)['used']['daily_requests'],0)
        self.assertEqual(self.guard.snapshot(fresh=True)['used']['minute_requests'],1)

    def test_project_model_key_and_free_tier_binding_fail_closed(self):
        key='synthetic-key-not-real';options=gemini_settings()
        self.assertEqual(gemini_eligible(options,None),'missing_api_key')
        options.update(account_plan='free',free_tier_confirmed=True,billing_disabled_confirmed=True)
        self.assertEqual(gemini_eligible(options,key),'quota_unverified')
        options.update(quota_verified=True,key_project_confirmed=True,api_project_id='test-project',quota_project_id='test-project',quota_key_sha256=hashlib.sha256(key.encode()).hexdigest())
        self.assertIsNone(gemini_eligible(options,key))
        for changed in [{'api_project_id':'other-project'},{'model':'other-model'},{'quota_key_sha256':'a'*64},{'account_plan':'paid'}]:
            self.assertIsNotNone(gemini_eligible({**options,**changed},key))

    def test_unsupported_daily_token_quota_and_paid_route_rejected(self):
        for changed in [{'max_daily_tokens':200000},{'max_minute_tokens':250000},{'free_only':False},{'thinking':'minimal'},{'max_minute_requests':6}]:
            with self.subTest(changed=changed),self.assertRaises(ValueError):gemini_settings(changed)

    def test_groq_rolling_recovery_is_not_an_invented_provider_midnight_reset(self):
        from jarvis.cloud_policy import settings
        options=settings({'safety_margin':.2},environ={})
        guard=CloudQuotaManager(Path(self.temp.name)/'groq.sqlite3',options,clock=lambda:self.now)
        first=self.now;identifier=guard.reserve(options['model'],100)
        guard.finish(identifier,{'total_tokens':50},{'x-ratelimit-remaining-requests':'700','x-ratelimit-reset-requests':'2h'})
        self.now+=61;snapshot=guard.snapshot(fresh=True)
        self.assertIsNone(snapshot['daily_reset_at'])
        self.assertEqual(snapshot['local_next_daily_recovery_at'],first+86400)
        self.assertEqual(snapshot['provider_request_reset_at'],first+7200)

    def test_visible_external_usage_cannot_spend_the_four_reserved_gemini_requests(self):
        self.guard.feedback('daily_requests',remaining=16,reset_at=self.now+3600)
        self.assertEqual(self.guard.snapshot(fresh=True)['remaining']['daily_requests'],12)
        self.guard.feedback('daily_requests',remaining=4,reset_at=self.now+3600)
        self.assertEqual(self.guard.snapshot(fresh=True)['remaining']['daily_requests'],0)
        with self.assertRaisesRegex(QuotaDenied,'daily_requests'):self.request()


if __name__=='__main__':unittest.main()
