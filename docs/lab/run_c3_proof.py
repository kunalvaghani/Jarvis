"""Actual C3 ingress/provider/theory proof, optional existing local-model proposals. No installs or global flag activation."""
import argparse,json,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
from jarvis.actions import Actions
from jarvis.engine import Engine
from jarvis.neural.service import BrainService
from jarvis.discovery.memory import LabMemory

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--local-hypotheses',action='store_true');parser.add_argument('--quick',action='store_true');parser.add_argument('--provided-hypotheses',action='store_true');args=parser.parse_args()
    base=ROOT/'app';config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'research':True,'sim':True}}
    s=BrainService(config,base/'.jarvis-runtime/lab-validation/c3-proof.sqlite3')
    a=Actions.__new__(Actions);a.config,a.base,a._neural_service,a.allowed_tools=config,base,s,None
    results=[];client=None;error=None
    out=ROOT/'docs/lab/evidence/c3-brain-proof.json'
    def run(goal):
        commands=[];e=Engine(commands.append,lambda *a:None);e.activate();e.feed(goal,final=True,raw=goal)
        if not commands:raise ValueError('ingress produced no command')
        started=time.monotonic();answer=a.execute(commands[0]);row=s.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
        import hashlib
        public_answer='\n'.join(line for line in answer.splitlines() if ' excerpt: ' not in line)
        results.append({'request':goal,'goal_id':row['goal_id'],'state':row['state'],'seconds':time.monotonic()-started,
                        'answer':public_answer,'actual_answer_sha256':hashlib.sha256(answer.encode()).hexdigest(),
                        'excerpt_policy':'Repeated publisher quotations omitted from public proof; exact locators/quotes remain in private Journal.'})
        if row['state']!='verified':raise ValueError('C3 goal did not verify')
        return answer
    try:
        run('lab lookup doi "10.1126/science.1192720"')
        run('lab research "Optical Clocks and Relativity"')
        before=len(s.journal.rows('SELECT id FROM discovery_literature_reads'))
        run('lab research "Optical Clocks and Relativity"')
        after=len(s.journal.rows('SELECT id FROM discovery_literature_reads'))
        if before!=after:raise ValueError('repeat research unexpectedly dispatched new HTTP reads')
        run('lab theory dilation "examples/discovery/clock-dilation.json"')
        if args.provided_hypotheses:
            import uuid
            row=s.journal.rows('SELECT id,ref FROM discovery_reviews ORDER BY rowid DESC LIMIT 1')[0]
            report=json.loads(s.journal.get(row['ref']))['review'];citation=report['citations'][-1]['id']
            proposals=[]
            for statement,prediction,is_null in (
                ('The apparent clock difference arises entirely from uncontrolled environmental or instrumental effects.',
                 'Matched environmental conditions and independent clock calibration remove the apparent difference.',True),
                ('Relative inertial motion causes the clock difference according to the special relativity model.',
                 'Changing relative velocity while controlling the environment changes the elapsed proper time.',False),
                ('A gravitational potential difference contributes to the observed clock difference.',
                 'Changing potential while controlling relative motion changes the clock comparison.',False)):
                proposals.append({'statement':statement,'prediction':prediction,'assumptions':['Primary methods and calibration must be checked independently.'],
                                  'citation_ids':[citation],'is_null':is_null})
            file=base/'.jarvis-runtime/lab-validation'/('c3-proposals-'+uuid.uuid4().hex+'.json')
            file.write_text(json.dumps({'review_id':row['id'],'tournament':{'hypotheses':proposals}}),encoding='utf-8')
            run('lab review hypotheses "'+file.relative_to(base).as_posix()+'"')
        if args.local_hypotheses:
            from jarvis.brain import BrainClient
            options=json.loads((base/'config/config.json').read_text(encoding='utf-8'))['brain']
            client=BrainClient(base,options);a.brain=SimpleNamespace(client=client)
            identity=s.journal.rows('SELECT id FROM discovery_reviews ORDER BY rowid DESC LIMIT 1')[0]['id']
            run('lab hypothesize '+('quick ' if args.quick else '')+'"'+identity+'"')
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc)[:500]}
    finally:
        if client:client.close()
        m=LabMemory(s.journal)
        result={'date_local':'2026-11-04 Asia/Calcutta','operator_assisted':True,'goals':results,'error':error,
                'typed_records':{k:len(m.list(k)) for k in ('Source','Claim','Hypothesis','RunArtifact')},
                'metadata_attempts':s.journal.rows('SELECT state,COUNT(*) AS count FROM discovery_literature_reads GROUP BY state'),
                'local_hypotheses_requested':args.local_hypotheses,'provided_hypotheses_requested':args.provided_hypotheses,'new_packages':0,'paid_provider_calls':0,
                'global_lab_flags':'unchanged false','microphone_and_live_UI':'NOT_RUN',
                'scope':'metadata/abstract citation provenance, candidate hypotheses, deterministic skeptic, conditional inertial SR; no full-text/physical proof'}
        out.write_text(json.dumps(result,indent=2),encoding='utf-8');s.journal.close()
        print(json.dumps({k:v for k,v in result.items() if k!='goals'}))
    return 1 if error else 0
if __name__=='__main__':raise SystemExit(main())
