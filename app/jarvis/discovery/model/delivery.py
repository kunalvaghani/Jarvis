"""Bounded D2 inputs and deterministic exports from authoritative scientific records."""
import hashlib,json,math,re
from decimal import Decimal
from typing import Literal
from pydantic import Field
from ..contracts import StrictModel,Identifier,RunArtifact,Experiment

DRIVE_ID=r'^[A-Za-z0-9_-]{10,100}$'

class Export(StrictModel):
    title: str=Field(min_length=1,max_length=120,pattern=r'^[^\r\n]+$')
    parent_id: str=Field(pattern=DRIVE_ID)
    artifact_id: Identifier | None=None
    experiment_ids: tuple[Identifier,...]=Field(default=(),max_length=8)
    metric: str=Field(default='period',pattern=r'^[a-z][a-z0-9_]{0,49}$')
    source_path: str=Field(default='metrics.measured_period_s',pattern=r'^metrics\.[a-z][a-z0-9_]{0,69}$')

class LongRead(StrictModel):
    source_file: str=Field(min_length=1,max_length=300)
    question: str=Field(min_length=4,max_length=240)
    budget: int=Field(default=6000,ge=1000,le=9000)

class Options(StrictModel):
    intent: str=Field(min_length=3,max_length=240)
    options: dict[str,str]=Field(min_length=1,max_length=8)

class BackgroundExport(StrictModel):
    query: str=Field(min_length=4,max_length=240)
    title: str=Field(min_length=1,max_length=120,pattern=r'^[^\r\n]+$')
    parent_id: str=Field(pattern=DRIVE_ID)

def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

def artifact(memory,identity):
    item=memory.get(identity)
    if not isinstance(item,RunArtifact) or not item.locator.startswith('artifact://sha256/'):raise ValueError('Journal-backed RunArtifact required')
    raw=memory.journal.get(item.locator)
    if raw is None or hashlib.sha256(raw.encode()).hexdigest()!=item.sha256:raise ValueError('scientific artifact hash differs')
    if len(raw)>60000:raise ValueError('export exceeds bounded text size')
    return item,raw

def literal(value):
    text=str(value)
    return "'"+text if text[:1] in ('=','+','-','@') else text

def prepare(memory,kind,request):
    spec=Export.model_validate_json(json.dumps(request));base={'kind':kind,'title':spec.title,'parent_id':spec.parent_id}
    if kind=='report':
        if spec.artifact_id is None or spec.experiment_ids:raise ValueError('one report artifact ID required')
        item,raw=artifact(memory,spec.artifact_id)
        text=(spec.title+'\nEvidence: '+item.evidence_status+'\nPhysical validation is not established by this export.\n'
              +'Source artifact: '+item.id+'\nSHA-256: '+item.sha256+'\n\n'+raw)
        return {**base,'text':text,'source_ids':list(item.source_ids),'input_refs':[item.locator]}
    if kind!='table' or not spec.experiment_ids or spec.artifact_id is not None:raise ValueError('bounded experiment IDs required for table')
    if len(set(spec.experiment_ids))!=len(spec.experiment_ids):raise ValueError('duplicate experiment IDs')
    rows=[['Experiment','Value','Unit','Evidence']];values=[];unit=None;refs=[];sources=[]
    for identity in spec.experiment_ids:
        experiment=memory.get(identity)
        if not isinstance(experiment,Experiment):raise ValueError('actual typed Experiment required')
        q=experiment.metrics.get(spec.metric)
        if q is None or q.value is None or q.origin not in ('solver','deterministic'):raise ValueError('known code/solver metric required')
        raw=memory.journal.get(q.source_ref)
        if raw is None:raise ValueError('metric Journal provenance missing')
        result=json.loads(raw);value=result
        if (result.get('solver')!=experiment.solver or result.get('solver_version')!=experiment.solver_version
                or result.get('design_sha256')!=experiment.design_sha256 or result.get('scenario_sha256')!=experiment.scenario_sha256):
            raise ValueError('metric source solver/design/scenario identity differs')
        for field in spec.source_path.split('.'):value=value[field]
        if type(value) not in (int,float) or not math.isfinite(value) or not math.isclose(value,q.value,rel_tol=1e-12,abs_tol=1e-12):
            raise ValueError('typed metric differs from explicit solver metric path')
        if unit is not None and unit!=q.unit:raise ValueError('table total requires matching units')
        unit=q.unit;values.append(str(q.value));refs.append(q.source_ref);sources+=list(experiment.source_ids)
        rows.append([literal(identity),str(q.value),literal(q.unit),literal(experiment.evidence_status)])
    rows.append(['Total',f'=SUM(B2:B{len(values)+1})',literal(unit),'Formula over recorded values; not a feasibility claim'])
    return {**base,'rows':rows,'expected_sum':str(sum(Decimal(v) for v in values)),
            'source_ids':sorted(set(sources)),'input_refs':refs}

def verify_back(payload,back):
    if payload['kind']=='report':
        # Drive's plain-text -> Docs importer inserts an extra empty paragraph at
        # a blank separator. Preserve every nonblank line/character; normalize
        # only line endings, outer whitespace and repeated empty paragraphs.
        def paragraphs(text):return re.sub(r'\n(?:[ \t]*\n)+','\n\n',text.replace('\r\n','\n').strip())
        if not isinstance(back,str) or paragraphs(back)!=paragraphs(payload['text']):raise ValueError('full Doc readback differs')
        return
    rows=payload['rows']
    if not isinstance(back,list) or len(back)!=len(rows):raise ValueError('Sheet readback row count differs')
    for i,(expected,actual) in enumerate(zip(rows,back)):
        if len(actual)!=len(expected):raise ValueError('Sheet readback column count differs')
        for col,(want,got) in enumerate(zip(expected,actual)):
            if col==1 and i>0:
                target=float(payload['expected_sum']) if i==len(rows)-1 else float(want)
                if not math.isclose(float(str(got).replace(',','')),target,rel_tol=1e-9,abs_tol=1e-9):raise ValueError('Sheet numeric/formula readback differs')
            elif str(got)!=str(want).removeprefix("'"):raise ValueError('Sheet literal readback differs')
