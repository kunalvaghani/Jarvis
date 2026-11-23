"""Anonymous, bounded official FIA edition discovery and source extraction.

URLs are discovered by Jarvis from the official index, never supplied by a
test operator. Unknown/changed text blocks the numeric contract; no defaults.
"""
import hashlib,io,json,re,urllib.request
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit

INDEX='https://www.fia.com/regulation/category/110/technical-regulations'
CAP=10_000_000


def allowed(url):
    p=urlsplit(url)
    return (p.scheme=='https' and p.hostname in ('www.fia.com','fia.com') and p.port in (None,443)
        and not p.username and not p.password and not p.query and not p.fragment
        and (url==INDEX or p.path.startswith(('/system/files/documents/','/sites/default/files/documents/'))))


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not allowed(newurl):raise ValueError('official source redirect left approved source paths')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(url,cap=CAP):
    if not allowed(url):raise ValueError('only official FIA source paths are allowed')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),OfficialRedirect())
    req=urllib.request.Request(url,headers={'User-Agent':'Jarvis-scientific-sources/1.0'})
    with opener.open(req,timeout=30) as response:
        raw=response.read(cap+1)
    if not raw or len(raw)>cap:raise ValueError('official source exceeds bounded read')
    return raw


class Links(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.href=None;self.words=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.href=dict(attrs).get('href');self.words=[]
    def handle_data(self,text):
        if self.href is not None:self.words.append(text)
    def handle_endtag(self,tag):
        if tag=='a' and self.href is not None:
            self.rows.append((urljoin(INDEX,self.href),' '.join(' '.join(self.words).split())))
            self.href=None


def document_season(title):
    """Read the regulation's named season, never a publication/copyright date."""
    match=re.search(r'\b(20\d{2})\s+(?:F1|Formula\s+(?:1|One))\b',title,re.I)
    if not match:raise ValueError('official regulation season identity missing')
    return int(match[1])


def edition(raw,year):
    parser=Links();parser.feed(raw.decode('utf-8'))
    options=[]
    for url,title in parser.rows:
        if not allowed(url) or not url.lower().endswith('.pdf'):continue
        try:season=document_season(title)
        except ValueError:continue
        if season!=year or 'technical' not in title.lower():continue
        issue=re.search(r'\bIss(?:ue)?\s*(\d+)\b',title,re.I)
        date=re.search(r'Published on (\d{2})\.(\d{2})\.(\d{4}|\d{2})\b',title,re.I)
        if not issue or not date:continue
        pub=f"{date[3] if len(date[3])==4 else '20'+date[3]}-{date[2]}-{date[1]}"
        if pub>datetime.now(timezone.utc).date().isoformat():continue
        options.append({'url':url,'title':title,'edition':int(issue[1]),'publication_date':pub,'year':year})
    if not options:raise ValueError('no dated official technical edition found for requested season')
    return max(options,key=lambda item:(item['publication_date'],item['edition']))


def extract(raw,year):
    if not raw.startswith(b'%PDF'):raise ValueError('regulation source is not a PDF')
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(raw))
    if reader.is_encrypted or not 5<=len(reader.pages)<=300:raise ValueError('unsupported regulation document')
    pages=[' '.join((page.extract_text() or '').split()) for page in reader.pages]
    text=' '.join(pages)
    if document_season(pages[0])!=year or 'technical' not in pages[0].lower():raise ValueError('wrong regulation PDF identity')
    # Extract only precise dimensional clauses; do not infer aerodynamic maps,
    # unknown internals or full regulatory compliance from these dimensions.
    wb=re.search(r'Wheelbase\s+(?:The\s+)?distance between the planes\s+XF\s*=\s*0 and XR\s*=\s*0 must '
        r'(?:not exceed|be less than or equal to)\s*(\d+)\s*mm',text,re.I)
    width=re.search(r'no part of the car may lie (?:outboard of Y\s*=\s*(\d+)|more than\s+(\d+)\s*mm from the plane Y\s*=\s*0)',text,re.I)
    if not wb or not width:raise ValueError('official dimension clauses changed; no numeric fallback permitted')
    limits={'maximum_wheelbase_m':int(wb[1])/1000,'maximum_non_tyre_half_width_m':int(width[1] or width[2])/1000}
    if not 2<=limits['maximum_wheelbase_m']<=5 or not .7<=limits['maximum_non_tyre_half_width_m']<=1.5:
        raise ValueError('extracted dimension units/domain invalid')
    active=year==2026
    if active and not all(s in text for s in ('Corner Mode','Straight Mode','Front Wing','Rear Wing')):
        raise ValueError('2026 active aero source clauses missing')
    locators={name:next(i+1 for i,page in enumerate(pages) if needle in page)
        for name,needle in [('wheelbase','Wheelbase'),('width','Width')]}
    return {'limits':limits,'active_aero':active,'page_locators':locators,
        'scope':'Only stated envelope dimensions and season-specific aero modes; not full FIA compliance or team engineering data.'}


def acquire(base,year):
    index=fetch(INDEX,2_000_000);record=edition(index,year);raw=fetch(record['url'])
    fields=extract(raw,year);root=Path(base)/'.jarvis-runtime/discovery/official-sources'
    from ...skill_memory import linked
    if any(linked(p) for p in (root,*root.parents)):raise ValueError('linked official-source cache refused')
    root.mkdir(parents=True,exist_ok=True)
    for body,suffix in ((index,'.html'),(raw,'.pdf')):
        digest=hashlib.sha256(body).hexdigest();path=root/(digest+suffix)
        if path.exists():
            if path.read_bytes()!=body:raise ValueError('immutable official source changed')
        else:
            with path.open('xb') as stream:stream.write(body)
    return {**record,**fields,'index_url':INDEX,'index_sha256':hashlib.sha256(index).hexdigest(),
        'sha256':hashlib.sha256(raw).hexdigest(),'cached_pdf':(root/(hashlib.sha256(raw).hexdigest()+'.pdf')).relative_to(base).as_posix(),
        'retrieved_at':datetime.now(timezone.utc).isoformat(),'license':'FIA copyright; retained for source verification, not licensed CAD',
        'content_is_untrusted':True}
