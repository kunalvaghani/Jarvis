"""Bounded, anonymous public metadata reads. No PDF, paid API or arbitrary URL fetch."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import re
import time
import uuid
from urllib.parse import quote, urlencode
import xml.etree.ElementTree as ET

from pydantic import Field
from ..contracts import StrictModel

LIMIT = 262144
HOSTS = {'crossref': 'api.crossref.org', 'arxiv': 'export.arxiv.org'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class Plain(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = Plain(); parser.feed(str(value or '')[:20000])
    return ' '.join(' '.join(parser.parts).split())[:8000]


def doi(value):
    value = str(value or '').strip().lower()
    value = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', value)
    if not re.fullmatch(r'10\.\d{4,9}/[^\s<>"?#]{1,180}', value):
        raise ValueError('invalid DOI')
    return value


def public_query(value):
    from ...neural.policy import SECRET_HINT
    if not isinstance(value, str) or not 4 <= len(value.strip()) <= 240:
        raise ValueError('public literature query must contain 4 to 240 characters')
    if SECRET_HINT.search(value) or re.search(r'https?://|[\w.+-]+@[\w.-]+|[\\{}\x00-\x1f]', value):
        raise ValueError('query must be a public topic, without secrets, addresses, paths or URLs')
    return value.strip()


class Paper(StrictModel):
    provider: str = Field(pattern='^(crossref|arxiv)$')
    identifier: str = Field(min_length=1, max_length=220)
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(min_length=1, max_length=500)
    doi: str | None = None
    published: str | None = Field(default=None, max_length=40)
    abstract: str = Field(default='', max_length=8000)
    authors: tuple[str, ...] = Field(default=(), max_length=20)
    publication_type: str = Field(default='unknown', max_length=100)
    retraction: str = Field(default='not_checked', pattern='^(not_checked|update_notice)$')
    license: str | None = Field(default=None, max_length=500)


def parse(provider, raw):
    if len(raw) > LIMIT: raise ValueError('metadata response too large')
    papers = []
    if provider == 'crossref':
        body = json.loads(raw); message = body['message']
        rows = message.get('items', []) if 'items' in message else [message]
        for row in rows[:4]:
            identity = doi(row['DOI']); title = plain((row.get('title') or [''])[0])
            date = row.get('published', {}).get('date-parts', [[]])[0]
            authors = tuple(plain(' '.join((a.get('given', ''), a.get('family', ''))))[:150] for a in row.get('author', [])[:20])
            notice = row.get('update-to') or row.get('updated-by') or row.get('relation', {}).get('is-retracted-by')
            papers.append(Paper(provider=provider, identifier=identity, doi=identity, title=title,
                url='https://doi.org/'+identity, published='-'.join(str(n) for n in date) or None,
                abstract=plain(row.get('abstract', '')), authors=authors,
                publication_type=str(row.get('type', 'unknown'))[:100],
                retraction='update_notice' if notice else 'not_checked'))
    elif provider == 'arxiv':
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper(): raise ValueError('XML declarations refused')
        ns = {'a':'http://www.w3.org/2005/Atom', 'x':'http://arxiv.org/schemas/atom'}
        for row in ET.fromstring(raw).findall('a:entry', ns)[:4]:
            identity = row.findtext('a:id', '', ns).rsplit('/abs/', 1)[-1]
            if not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?', identity): raise ValueError('invalid arXiv identity')
            value = row.findtext('x:doi', '', ns)
            papers.append(Paper(provider=provider, identifier=identity, doi=doi(value) if value else None,
                title=plain(row.findtext('a:title', '', ns)), url='https://arxiv.org/abs/'+identity,
                abstract=plain(row.findtext('a:summary', '', ns)), published=row.findtext('a:published', None, ns),
                authors=tuple(plain(a.findtext('a:name', '', ns))[:150] for a in row.findall('a:author', ns)[:20]),
                publication_type='preprint'))
    else: raise ValueError('unknown or metered provider; no fallback')
    return papers


def fetch(url, cancelled):
    """Exact provider URLs only; environment credentials/proxies and redirects disabled."""
    from urllib.parse import urlsplit
    import requests
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in HOSTS.values() or parts.username or parts.port:
        raise ValueError('metadata endpoint not allowed')
    started = time.monotonic()
    with requests.Session() as session:
        session.trust_env = False
        with session.get(url, headers={'User-Agent':'Jarvis-Discovery-Lab/1.0 (bounded metadata research)'},
                         timeout=(5, 10), allow_redirects=False, stream=True) as response:
            if response.status_code != 200: raise ValueError('metadata HTTP status '+str(response.status_code)+'; no automatic retry')
            chunks = []; size = 0
            for chunk in response.iter_content(8192):
                if cancelled() or time.monotonic()-started > 20: raise ValueError('metadata cancelled or deadline exceeded')
                size += len(chunk)
                if size > LIMIT: raise ValueError('metadata response cap exceeded')
                chunks.append(chunk)
            return b''.join(chunks)


def read(journal, provider, query, *, cancelled=lambda:False, lookup=False):
    """One persisted attempt before a read; cached raw response lives in the existing Journal."""
    if cancelled(): raise ValueError('cancelled before literature read')
    if provider not in HOSTS: raise PermissionError('unapproved/metered provider unavailable')
    query = doi(query) if lookup else public_query(query)
    if lookup and provider != 'crossref': raise ValueError('DOI lookup uses Crossref')
    key = digest([provider, query, lookup]); now = time.time()
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_literature_reads (id TEXT PRIMARY KEY, cache_key TEXT NOT NULL, created REAL NOT NULL, ref TEXT, state TEXT NOT NULL)')
        old = db.execute("SELECT ref FROM discovery_literature_reads WHERE cache_key=? AND state='done' AND created>? ORDER BY created DESC LIMIT 1", (key, now-86400)).fetchone()
        if not old:
            pending = db.execute("SELECT id FROM discovery_literature_reads WHERE cache_key=? AND state!='done' AND created>? LIMIT 1",(key,now-300)).fetchone()
            if pending: raise ValueError('recent failed/unfinished metadata request; no automatic redispatch during five-minute cooldown')
            count = db.execute('SELECT COUNT(*) FROM discovery_literature_reads WHERE created>?', (now-86400,)).fetchone()[0]
            if count >= 50: raise PermissionError('50 public metadata attempts in rolling day exhausted')
            identity = uuid.uuid4().hex
            db.execute('INSERT INTO discovery_literature_reads VALUES (?,?,?,?,?)', (identity,key,now,None,'started'))
    if old:
        cached = json.loads(journal.get(old[0])); return cached, True
    # IDs/query are serialized before the network call; no arbitrary link from a provider is followed.
    request = {'provider':provider,'query':query,'lookup':lookup}; request_ref=journal.put(request, data_type='Report')
    with journal.tx() as db: db.execute('UPDATE discovery_literature_reads SET ref=? WHERE id=?',(request_ref,identity))
    if provider == 'crossref':
        url = 'https://api.crossref.org/works/'+quote(query, safe='') if lookup else 'https://api.crossref.org/works?'+urlencode({'query.bibliographic':query,'rows':4})
    else:
        url = 'https://export.arxiv.org/api/query?'+urlencode({'search_query':'all:"'+query.replace('"','')+'"','max_results':4})
    # Respect arXiv's interval across concurrent jobs using the same Journal; no busy loop/retry.
    if provider == 'arxiv':
        with journal.tx() as db:
            recent = db.execute("SELECT COUNT(*) FROM discovery_literature_reads WHERE id!=? AND created>?", (identity,now-3)).fetchone()[0]
        if recent: raise ValueError('arXiv request interval not yet available; use cached result or try later')
    try:
        raw = fetch(url, cancelled)
        papers = parse(provider, raw)
        if lookup and (len(papers)!=1 or papers[0].doi!=query):
            raise ValueError('DOI lookup returned a different or ambiguous identity')
    except Exception as error:
        reason='HTTP_'+str(error).split()[3].split(';')[0] if isinstance(error,ValueError) and str(error).startswith('metadata HTTP status ') else type(error).__name__
        failure_ref=journal.put({'request_ref':request_ref,'state':'failed','reason':reason},data_type='Report')
        with journal.tx() as db: db.execute("UPDATE discovery_literature_reads SET state='failed',ref=? WHERE id=?",(failure_ref,identity))
        raise
    result = {'request':request,'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),
              'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_utf8':raw.decode('utf-8'),
              'papers':[p.model_dump(mode='json') for p in papers]}
    ref = journal.put(result, data_type='Report')
    with journal.tx() as db: db.execute("UPDATE discovery_literature_reads SET ref=?,state='done' WHERE id=?", (ref, identity))
    return result, False
