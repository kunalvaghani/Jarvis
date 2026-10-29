"""Cross-process SQLite reservations; conservative rolling windows, no LLM counting."""
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
import copy
import threading


class QuotaDenied(ValueError):
    pass


def duration(value):
    if not isinstance(value,str) or len(value)>64: return None
    parts=re.findall(r'(\d+(?:\.\d+)?)(ms|s|m|h|d)',value)
    if not parts or ''.join(a+b for a,b in parts)!=value: return None
    result=sum(float(a)*{'ms':.001,'s':1,'m':60,'h':3600,'d':86400}[b] for a,b in parts)
    return min(86400,max(1,result))


class QuotaGuardian:
    def __init__(self, path, options, clock=time.time):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.options,self.clock=options,clock
        self.cached=None;self.cache_until=0.;self.cached_clock=0.;self.cache_lock=threading.Lock()
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, at REAL, model TEXT, reserved INTEGER, tokens INTEGER, status TEXT, usage TEXT, response_id TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS calls_at ON calls(at)')
            db.execute('CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=.25)
        db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    @staticmethod
    def state(db,key,default=None):
        row=db.execute('SELECT value FROM state WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def put(db,key,value):
        db.execute('INSERT OR REPLACE INTO state VALUES (?,?)',(key,json.dumps(value)))

    def confirm_clock(self, server_time):
        self.cache_until=0
        now=self.clock()
        if abs(now-server_time)>120: raise QuotaDenied('provider_clock_disagreement')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.put(db,'clock_verified',now)
            self.put(db,'last_clock',now)

    def _snapshot(self,db,now):
        last=self.state(db,'last_clock',now)
        if now < last-1 or (now-last>300 and now-self.state(db,'clock_verified',0)>300):
            raise QuotaDenied('clock_change_requires_metadata')
        if self.state(db,'unsafe',False):
            # A token-estimation overrun must not disable cloud forever. Keep
            # its full actual charge until it ages out of the daily window.
            # Derive this from durable rows instead of clearing a shared flag,
            # which could race another worker's newly recorded overrun.
            overrun=db.execute('SELECT MAX(at) FROM calls WHERE tokens>reserved').fetchone()[0]
            if overrun is None: raise QuotaDenied('unknown_usage_requires_review')
            if overrun>now-86400: raise QuotaDenied('usage_overrun_waiting_for_daily_window')
        if now < self.state(db,'blocked_until',0): raise QuotaDenied('provider_backoff')
        rows=db.execute('SELECT at,tokens,status FROM calls WHERE at>?',(now-86400,)).fetchall()
        minute=[r for r in rows if r['at']>now-60 or r['status']=='reserved']
        used={'daily_requests':len(rows),'daily_tokens':sum(r['tokens'] for r in rows),
              'minute_requests':len(minute),'minute_tokens':sum(r['tokens'] for r in minute)}
        budgets={k:int(self.options['max_'+k]*(1-self.options['safety_margin']))-v for k,v in used.items()}
        for kind,key in [('daily_requests','requests'),('minute_tokens','tokens')]:
            limit=self.state(db,'provider_limit_'+key)
            if limit is not None: budgets[kind]=min(budgets[kind],int(limit*(1-self.options['safety_margin']))-used[kind])
            header=self.state(db,'header_'+key)
            if header and now<header['until']:
                subsequent=db.execute('SELECT COUNT(*),COALESCE(SUM(tokens),0) FROM calls WHERE (at>=? OR status=?) AND id!=?',(header['at'],'reserved',header['id'])).fetchone()
                budgets[kind]=min(budgets[kind],header['remaining']-subsequent[0 if key=='requests' else 1])
        fraction=min(budgets[k]/max(1,self.options['max_'+k]) for k in budgets)
        state='EXHAUSTED' if min(budgets.values())<=0 else 'CRITICAL' if fraction<.1 else 'CONSERVE' if fraction<.3 else 'NORMAL'
        return {'state':state,'remaining':budgets,'used':used,'scope':'Local conservative rolling 24-hour/60-second ledger; provider request headers are daily, token headers minute-level.'}

    def snapshot(self, fresh=False):
        # Advisory only. Every real dispatch rechecks under BEGIN IMMEDIATE.
        # Other processes can change the ledger; stale hints never authorize I/O.
        with self.cache_lock:
            if not fresh and self.cached is not None and time.monotonic()<self.cache_until and 0<=self.clock()-self.cached_clock<.25:
                return copy.deepcopy(self.cached)
        try:
            with self.connect() as db: value=self._snapshot(db,self.clock())
        except (sqlite3.Error,ValueError,TypeError) as error:
            value={'state':'UNKNOWN','remaining':{},'scope':'No cloud dispatch until ledger/clock state is safe.',
                   'reason':str(error) if isinstance(error,QuotaDenied) else 'quota_storage_unavailable'}
            if value['reason']=='provider_backoff':
                try:
                    with self.connect() as db:
                        value['cooldown_until']=self.state(db,'blocked_until')
                        value['exhausted_dimension']=self.state(db,'exhausted_dimension','provider_unspecified')
                except sqlite3.Error:pass
        with self.cache_lock:
            self.cached=value;self.cache_until=time.monotonic()+.25;self.cached_clock=self.clock()
        return copy.deepcopy(value)

    def admit(self, db, now, model, task_id, task_limit):
        """Additional provider scope/concurrency gates share the reservation transaction."""

    def reserve(self, model, amount, request_id=None, input_tokens=None, output_tokens=None, task_id=None, task_limit=None):
        self.cache_until=0
        if type(amount) is not int or amount<1: raise QuotaDenied('invalid_token_estimate')
        if any(value is not None and (type(value) is not int or not 0 <= value <= amount)
               for value in (input_tokens,output_tokens)):
            raise QuotaDenied('invalid_token_estimate')
        try:
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                now=self.clock(); snap=self._snapshot(db,now)
                for kind,remaining in snap['remaining'].items():
                    required=(input_tokens if input_tokens is not None else amount) if kind.endswith('input_tokens') else amount if kind.endswith('tokens') else 1
                    if remaining < required: raise QuotaDenied('quota_'+kind)
                self.admit(db,now,model,task_id,task_limit)
                identifier=request_id or uuid.uuid4().hex
                if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier): raise QuotaDenied('invalid_request_id')
                if db.execute('SELECT 1 FROM calls WHERE id=?',(identifier,)).fetchone(): raise QuotaDenied('duplicate_cloud_dispatch_refused')
                estimate={'estimated_total_tokens':amount,'provider':self.options.get('provider','groq')}
                if task_id is not None:
                    if not isinstance(task_id,str) or not re.fullmatch('[a-f0-9]{32,64}',task_id):raise QuotaDenied('invalid_task_scope')
                    estimate['task_id']=task_id
                if input_tokens is not None: estimate['estimated_input_tokens']=input_tokens
                if output_tokens is not None: estimate['reserved_output_tokens']=output_tokens
                db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?,?)',(identifier,now,model,amount,amount,'reserved',json.dumps(estimate),''))
                self.put(db,'last_clock',now)
                return identifier
        except sqlite3.Error: raise QuotaDenied('quota_storage_unavailable') from None

    def finish(self, identifier, usage=None, headers=None, status='complete', response_id=''):
        self.cache_until=0
        usage=usage if isinstance(usage,dict) else {}
        safe={k:usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens') if type(usage.get(k)) is int and usage[k]>=0}
        exact=safe.get('total_tokens')
        # Missing, zero or malformed metering must not refund submitted work.
        # A successful text completion consumes positive tokens; a zero report
        # is conservatively uncertain even if the provider did not bill it.
        if exact == 0 or any(k in usage and k not in safe for k in ('prompt_tokens','completion_tokens','total_tokens')):
            exact=None
        if exact is not None and exact < safe.get('prompt_tokens',0)+safe.get('completion_tokens',0): exact=None
        from .cloud_policy import SECRET
        response_id=response_id if isinstance(response_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',response_id) and not SECRET.search(response_id) else ''
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM calls WHERE id=?',(identifier,)).fetchone()
            if row is None or row['status']!='reserved': return  # idempotent
            total=exact if exact is not None else row['reserved']
            metadata={**json.loads(row['usage']),**safe,'exact_usage_available':exact is not None}
            if total>row['reserved']: self.put(db,'unsafe',True)
            db.execute('UPDATE calls SET tokens=?,status=?,usage=?,response_id=?,at=? WHERE id=?',
                (total,status if exact is not None else 'uncertain',json.dumps(metadata),str(response_id)[:100],row['at'] if self.options.get('keep_dispatch_time') else self.clock(),identifier))
            normalized={str(k).lower():str(v) for k,v in (headers or {}).items()}
            for key in ('requests','tokens'):
                limit=normalized.get('x-ratelimit-limit-'+key)
                if limit is not None and limit.isdigit():
                    prior_limit=self.state(db,'provider_limit_'+key,int(limit))
                    self.put(db,'provider_limit_'+key,min(prior_limit,int(limit)))
                remaining=normalized.get('x-ratelimit-remaining-'+key)
                reset=duration(normalized.get('x-ratelimit-reset-'+key))
                if remaining is not None and remaining.isdigit():
                    now=self.clock(); prior=self.state(db,'header_'+key)
                    value=int(remaining)
                    if prior and now<prior['until']: value=min(value,prior['remaining'])
                    self.put(db,'header_'+key,{'remaining':value,'until':now+(reset or (86400 if key=='requests' else 60)), 'at':now,'id':identifier})
                    if value==0:self.put(db,'exhausted_dimension','daily_requests' if key=='requests' else 'minute_tokens')

    def block(self, seconds):
        self.cache_until=0
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.put(db,'blocked_until',max(self.state(db,'blocked_until',0),self.clock()+max(1,min(86400,seconds))))


class CloudQuotaManager(QuotaGuardian):
    """Extend the existing durable ledger for project/model scopes and input quotas.

    Groq uses its existing organization ledger. Gemini gets a ledger named by
    its confirmed project/model binding; daily tokens have no invented limit.
    """
    def _snapshot(self, db, now):
        from datetime import datetime, timedelta, timezone
        last=self.state(db,'last_clock',now)
        if now<last-1 or now-last>300 and now-self.state(db,'clock_verified',0)>300:raise QuotaDenied('clock_change_requires_metadata')
        if now<self.state(db,'blocked_until',0):raise QuotaDenied('provider_backoff')
        if self.options.get('daily_reset')=='America/Los_Angeles':
            try:
                from zoneinfo import ZoneInfo
                zone=ZoneInfo('America/Los_Angeles')
            except (ImportError,KeyError):
                from dateutil.tz import gettz
                zone=gettz('America/Los_Angeles')
                if zone is None:raise QuotaDenied('timezone_unavailable')
            day=datetime.fromtimestamp(now,zone).replace(hour=0,minute=0,second=0,microsecond=0)
            start=day.timestamp();reset=(day+timedelta(days=1)).timestamp()
        else:start=now-86400;reset=None
        if self.options.get('max_daily_tokens') is not None and self.state(db,'unsafe',False):
            overrun=db.execute('SELECT MAX(at) FROM calls WHERE tokens>reserved').fetchone()[0]
            if overrun is None or overrun>=start:raise QuotaDenied('usage_overrun_waiting_for_daily_window')
        rows=db.execute('SELECT * FROM calls WHERE at>=?',(min(start,now-60),)).fetchall()
        daily=[row for row in rows if row['at']>=start]
        minute=[row for row in rows if row['at']>now-60 or row['status']=='reserved' and now-row['at']<self.options.get('timeout_seconds',120)+30]
        def input_charge(row):
            usage=json.loads(row['usage']);value=usage.get('prompt_tokens')
            return value if type(value) is int and value>0 else usage.get('estimated_input_tokens',row['reserved'])
        used={'daily_requests':len(daily),'daily_tokens':sum(row['tokens'] for row in daily),
              'minute_requests':len(minute),'minute_tokens':sum(row['tokens'] for row in minute),
              'minute_input_tokens':sum(input_charge(row) for row in minute)}
        limits={key:self.options.get('max_'+key) for key in used}
        remaining={key:int(value*(1-self.options['safety_margin']))-used[key] for key,value in limits.items() if value is not None}
        for key in remaining:
            cap=self.state(db,'effective_limit_'+key)
            if cap is not None:remaining[key]=min(remaining[key],int(cap*(1-self.options['safety_margin']))-used[key])
            feedback=self.state(db,'remaining_'+key)
            if feedback and now<feedback['until']:
                subsequent=[row for row in rows if row['at']>=feedback['at'] and row['id']!=feedback.get('request_id')]
                charge=sum(input_charge(row) if key.endswith('input_tokens') else row['tokens'] for row in subsequent) if key.endswith('tokens') else len(subsequent)
                provider_limit=self.state(db,'effective_limit_'+key,limits[key])
                headroom=provider_limit-int(provider_limit*(1-self.options['safety_margin']))
                remaining[key]=min(remaining[key],feedback['remaining']-headroom-charge)
        # Legacy Groq header accounting shares the same state and reservations.
        for key,dimension in [('requests','daily_requests'),('tokens','minute_tokens')]:
            if dimension not in remaining:continue
            cap=self.state(db,'provider_limit_'+key)
            if cap is not None:remaining[dimension]=min(remaining[dimension],int(cap*(1-self.options['safety_margin']))-used[dimension])
            header=self.state(db,'header_'+key)
            if header and now<header['until']:
                subsequent=[row for row in rows if (row['at']>=header['at'] or row['status']=='reserved') and row['id']!=header['id']]
                provider_limit=self.state(db,'provider_limit_'+key,limits[dimension])
                headroom=provider_limit-int(provider_limit*(1-self.options['safety_margin']))
                remaining[dimension]=min(remaining[dimension],header['remaining']-headroom-(len(subsequent) if key=='requests' else sum(row['tokens'] for row in subsequent)))
        fraction=min((remaining[key]/max(1,limits[key]) for key in remaining),default=0)
        state='EXHAUSTED' if min(remaining.values(),default=0)<=0 else 'CRITICAL' if fraction<.1 else 'CONSERVE' if fraction<.3 else 'NORMAL'
        return {'state':state,'remaining':{key:max(0,value) for key,value in remaining.items()},'used':used,
                'daily_reset_at':reset,'daily_reset_timezone':self.options.get('daily_reset','rolling_24h'),
                'local_next_daily_recovery_at':min((row['at']+86400 for row in daily),default=None) if reset is None else reset,
                'provider_request_reset_at':self.state(db,'header_requests',{}).get('until'),
                'provider_token_reset_at':self.state(db,'header_tokens',{}).get('until'),
                'scope':'Local reservations at configured project/model scope; external usage is unknown except explicit provider feedback.'}

    def task_usage(self,task_id):
        if not isinstance(task_id,str) or not re.fullmatch('[a-f0-9]{32,64}',task_id):raise QuotaDenied('invalid_task_scope')
        with self.connect() as db:
            return sum(json.loads(row['usage']).get('task_id')==task_id for row in db.execute('SELECT usage FROM calls'))

    def admit(self,db,now,model,task_id,task_limit):
        if model!=self.options['model']:raise QuotaDenied('model_quota_scope_mismatch')
        active=db.execute('SELECT COUNT(*) FROM calls WHERE status=? AND at>?',('reserved',now-self.options.get('timeout_seconds',120)-30)).fetchone()[0]
        if active>=self.options.get('max_concurrent_calls',1):raise QuotaDenied('concurrent_inference_limit')
        if task_limit is not None:
            if type(task_limit) is not int or not 1<=task_limit<=16 or task_id is None:raise QuotaDenied('invalid_task_limit')
            rows=db.execute('SELECT usage FROM calls').fetchall()
            if sum(json.loads(row['usage']).get('task_id')==task_id for row in rows)>=task_limit:raise QuotaDenied('task_call_limit')

    def feedback(self,dimension,*,limit=None,remaining=None,reset_at=None,request_id=None):
        if dimension not in {'minute_requests','daily_requests','minute_tokens','daily_tokens','minute_input_tokens'}:raise QuotaDenied('unsupported_quota_dimension')
        if any(value is not None and (type(value) is not int or value<0) for value in (limit,remaining)):raise QuotaDenied('invalid_quota_feedback')
        self.cache_until=0
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if limit is not None:self.put(db,'effective_limit_'+dimension,min(limit,self.state(db,'effective_limit_'+dimension,limit)))
            if remaining is not None:
                now=self.clock()
                if reset_at is None or not now<reset_at<=now+172800:raise QuotaDenied('invalid_quota_reset')
                prior=self.state(db,'remaining_'+dimension)
                if prior and now<prior['until']:remaining=min(remaining,prior['remaining'])
                self.put(db,'remaining_'+dimension,{'remaining':remaining,'until':reset_at,'at':now,'request_id':request_id})
                if remaining==0:self.put(db,'exhausted_dimension',dimension)
