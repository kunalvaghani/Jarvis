"""Extractive evidence audit and deterministic skeptic. Ranking is not scientific truth."""
import json
import re
from pydantic import Field, model_validator
from ..contracts import Identifier,StrictModel
from ..adapters.literature import Paper, digest


class Proposal(StrictModel):
    statement: str = Field(min_length=15, max_length=900)
    prediction: str = Field(min_length=15, max_length=900)
    assumptions: tuple[str, ...] = Field(min_length=1, max_length=5)
    citation_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    is_null: bool


class Tournament(StrictModel):
    hypotheses: tuple[Proposal, ...] = Field(min_length=3, max_length=6)

    @model_validator(mode='after')
    def competitors(self):
        if sum(h.is_null for h in self.hypotheses) != 1:
            raise ValueError('exactly one explicit null and at least two alternatives required')
        texts = [' '.join(h.statement.casefold().split()) for h in self.hypotheses]
        if len(set(texts)) != len(texts): raise ValueError('hypotheses must differ')
        return self


class Dossier(StrictModel):
    review_id: Identifier
    tournament: Tournament


def review(question, responses):
    from ...neural.adapters import _relevant
    from ...control.web.scouts import brief
    found = {}; merged = []
    for response in responses:
        for raw in response['papers']:
            paper = Paper.model_validate_json(json.dumps(raw))
            key = paper.doi or paper.provider+':'+paper.identifier
            if key in found:
                previous = found[key]
                # Preserve every provider's provenance; prefer the longer available abstract only.
                merged.append({'identity':key,'providers':[previous['provider'],paper.provider]})
                if len(paper.abstract) <= len(previous['abstract']): continue
            found[key] = paper.model_dump(mode='json')
    citations = []; excerpts = []
    for identity, paper in list(found.items())[:8]:
        citation = 'paper-'+digest([identity,digest(paper)])[:24]
        text = paper['abstract']
        selected = _relevant(text, question, limit=2000) if text else ''
        # One contiguous <=24-word excerpt per paper; never a synthesized scientific assertion.
        first = re.split(r'(?<=[.!?])\s+', selected)[0] if selected else ''
        excerpt = ' '.join(first.split()[:24])
        if excerpt and excerpt not in text:
            excerpt = ' '.join(text.split()[:24])
        loc = text.find(excerpt) if excerpt else -1
        citations.append({'id':citation,'identity':identity,'paper':paper,
                          'content_sha256':digest(paper),'abstract_only':True,
                          'peer_review':'not_verified','retraction_status':paper['retraction']})
        if excerpt and loc >= 0 and paper['retraction']=='not_checked':
            excerpts.append({'citation_id':citation,'quote':excerpt,'start':loc,'end':loc+len(excerpt),
                             'evidence_status':'INSUFFICIENT_EVIDENCE','kind':'source_excerpt_not_verified_fact'})
    # Heuristic pairs are questions for review, never asserted contradiction edges.
    candidate_pairs = []
    for i,a in enumerate(excerpts):
        for b in excerpts[i+1:]:
            words = lambda s:set(re.findall(r'[a-z]{3,}',s.lower()))
            wa,wb=words(a['quote']),words(b['quote'])
            neg = lambda s:bool(re.search(r'\b(?:no|not|cannot|never|without)\b',s,re.I))
            if len(wa & wb)/max(1,len(wa | wb)) >= .45 and neg(a['quote']) != neg(b['quote']):
                candidate_pairs.append({'citations':[a['citation_id'],b['citation_id']],
                    'state':'POSSIBLE_CONTRADICTION_REQUIRES_CONTEXT_REVIEW'})
    # Existing CPU scouts are used to prepare a bounded map, with no Laya/model invocation.
    page='title Literature source map\n'+'\n'.join('article "'+c['paper']['title'].replace('"', "'")+'"\n  paragraph "'+c['paper']['abstract'].replace('"', "'")+'"' for c in citations)
    return {'question':question,'citations':citations,'excerpts':excerpts,'duplicate_identities':merged,
            'possible_contradictions':candidate_pairs,'source_map':brief(question,page,budget=6000),
            'coverage':'provider metadata/available abstracts; no full-text or independent retraction guarantee',
            'evidence_status':'INSUFFICIENT_EVIDENCE','justification':'Citations establish source provenance, not physical truth.'}


def audit_hypotheses(report):
    """Transparent evidence-review alternatives, not invented domain mechanisms."""
    ids=tuple(c['id'] for c in report['citations'])
    if not ids: raise ValueError('no usable citations for hypothesis review')
    assumptions=('Retrieved metadata may be incomplete; full methods and independent measurements have not been checked.',)
    return Tournament(hypotheses=(
        Proposal(statement='The retrieved sources are insufficient to discriminate the proposed scientific mechanisms.',
                 prediction='Independent methods and measurement evidence will be needed before a mechanism can be selected.',assumptions=assumptions,citation_ids=ids,is_null=True),
        Proposal(statement='Apparent differences between source summaries reflect different experimental contexts or assumptions.',
                 prediction='Comparing matched conditions and methods will remove the apparent disagreement.',assumptions=assumptions,citation_ids=ids,is_null=False),
        Proposal(statement='The source summaries contain a substantive disagreement that survives matching their contexts.',
                 prediction='A matched-condition comparison of the primary methods will retain opposing predictions.',assumptions=assumptions,citation_ids=ids,is_null=False)))


def skeptic(report, tournament):
    available={c['id']:c for c in report['citations']}; rows=[]
    for h in tournament.hypotheses:
        prose=' '.join((h.statement,h.prediction,*h.assumptions))
        if re.search(r'\d|\b(?:proven|guaranteed|experimentally verified)\b',prose,re.I):
            raise ValueError('unverified numeric/proof claims are not accepted from hypothesis text')
        if any(i not in available for i in h.citation_ids): raise ValueError('hypothesis cites an unknown source')
        if any(available[i]['retraction_status']!='not_checked' for i in h.citation_ids):
            raise ValueError('hypothesis relies on a flagged update/retraction record')
        rows.append({'proposal':h.model_dump(mode='json'),'evidence_status':'UNVERIFIED_SPECULATION',
            'priority_score':len(set(h.citation_ids)), 'score_meaning':'citation coverage only; not probability, correctness or physical support',
            'criticisms':['Citation existence does not establish entailment.',
                          'Check governing equations, units, energy/conservation, stability and causal assumptions in a domain test.',
                          'Obtain full methods and an independently measured baseline before causal conclusions.']})
    rows.sort(key=lambda r:-r['priority_score'])
    return rows


def verify(report, responses, tournament, ranked):
    expected=review(report['question'],responses)
    if expected!=report or skeptic(report,tournament)!=ranked:
        raise ValueError('citation/excerpt/hash/score replay differs')
    for e in report['excerpts']:
        paper=next(c['paper'] for c in report['citations'] if c['id']==e['citation_id'])
        if paper['abstract'][e['start']:e['end']] != e['quote'] or len(e['quote'].split())>24:
            raise ValueError('citation locator or quote is not grounded')
    return True
