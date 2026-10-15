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
        except (sqlite3.Error,ValueError,TypeError):
            value={'state':'UNKNOWN','remaining':{},'scope':'No cloud dispatch until ledger/clock state is safe.'}
        with self.cache_lock:
            self.cached=value;self.cache_until=time.monotonic()+.25;self.cached_clock=self.clock()
        return copy.deepcopy(value)

    def reserve(self, model, amount, request_id=None, input_tokens=None, output_tokens=None):
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
                    if remaining < (amount if kind.endswith('tokens') else 1): raise QuotaDenied('quota_'+kind)
                identifier=request_id or uuid.uuid4().hex
                if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier): raise QuotaDenied('invalid_request_id')
                if db.execute('SELECT 1 FROM calls WHERE id=?',(identifier,)).fetchone(): raise QuotaDenied('duplicate_cloud_dispatch_refused')
                estimate={'estimated_total_tokens':amount,'provider':'groq'}
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
                (total,status if exact is not None else 'uncertain',json.dumps(metadata),str(response_id)[:100],self.clock(),identifier))
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

    def block(self, seconds):
        self.cache_until=0
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.put(db,'blocked_until',max(self.state(db,'blocked_until',0),self.clock()+max(1,min(86400,seconds))))
