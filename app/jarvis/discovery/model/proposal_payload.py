"""Compact local proposals; code, not a model, binds citations/null/evidence status."""
from pydantic import Field
from ..contracts import StrictModel
from .literature_review import Proposal,Tournament,audit_hypotheses,skeptic

from ..proposal_wire import SYSTEM


class Seed(StrictModel):
    statement: str = Field(min_length=15,max_length=100)
    prediction: str = Field(min_length=15,max_length=140)


class Seeds(StrictModel):
    alternatives: tuple[Seed,...] = Field(min_length=2,max_length=2)


def expand(report,reply):
    seeds=Seeds.model_validate_json(__import__('json').dumps({k:v for k,v in reply.items() if k!='model_used'}))
    citations=tuple(c['id'] for c in context(report)['citations'])
    baseline=audit_hypotheses(report).hypotheses[0]
    hypotheses=[baseline]
    for seed in seeds.alternatives:
        hypotheses.append(Proposal(statement=seed.statement,prediction=seed.prediction,
            assumptions=('Proposed mechanism is unverified; citations identify context and do not establish entailment.',),
            citation_ids=citations,is_null=False))
    result=Tournament(hypotheses=tuple(hypotheses));skeptic(report,result)
    return result


def context(report):
    """Fit the explicit small-model context; disclose exactly which sources were shown."""
    quoted={e['citation_id'] for e in report.get('excerpts',[])}
    selected=sorted(report['citations'],key=lambda c:c['id'] not in quoted)[:3]
    ids={c['id'] for c in selected}
    return {'question':report['question'][:240],
            'citations':[{'id':c['id'],'title':c['paper']['title'][:160]} for c in selected],
            'excerpts':[e for e in report.get('excerpts',[]) if e['citation_id'] in ids][:3],
            'coverage':'bounded metadata/excerpts only; citations do not establish support'}
