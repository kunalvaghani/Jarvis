"""Persistent repository knowledge, lifecycle and permission-aware dispatch.

Only metadata is loaded in Jarvis. Repository modules never enter sys.modules here.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time

from .repo_acquisition import acquire,verify_snapshot,identity,git
from .repo_analysis import analyze,validate
from .repo_sandbox import RepositorySandbox
from .skill_memory import linked,words

STATES={'ANALYZED','VALIDATED','APPROVED','ACTIVE','QUARANTINED','FAILED','DISABLED','REVOKED'}


def now():return datetime.now(timezone.utc).isoformat()


class RepositorySkills:
    def __init__(self,base,options=None,memory=None,report=lambda *args:None):
        options=options or {}
        if not isinstance(options,dict) or set(options)-{'enabled','image'}:raise ValueError('Invalid repository_skills configuration.')
        if type(options.get('enabled',True)) is not bool:raise ValueError('repository_skills.enabled must be boolean.')
        self.enabled=options.get('enabled',True);self.base=Path(base).absolute()
        self.vault=self.base/'.jarvis-runtime/repository-skills';self.vault.mkdir(parents=True,exist_ok=True)
        if any(linked(p) for p in [self.vault,*self.vault.parents]):raise ValueError('Repository registry path must not be linked.')
        self.path=self.vault/'registry.sqlite3';self.memory=memory;self.report=report
        self.runtime=RepositorySandbox(options.get('image','jarvis-repository-runtime:1'))
        self.learning=threading.RLock();self.executions=threading.RLock()
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS repositories(id TEXT PRIMARY KEY, identity TEXT NOT NULL, current_revision TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS revisions(repo_id TEXT NOT NULL, revision TEXT NOT NULL, snapshot TEXT NOT NULL, knowledge TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(repo_id,revision));
                CREATE TABLE IF NOT EXISTS skills(id TEXT PRIMARY KEY, repo_id TEXT NOT NULL, revision TEXT NOT NULL, entity TEXT NOT NULL, state TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0, validation TEXT, updated TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS skills_by_repo_state ON skills(repo_id,state);
                CREATE TABLE IF NOT EXISTS outcomes(id INTEGER PRIMARY KEY, skill_id TEXT NOT NULL, at TEXT NOT NULL, outcome TEXT NOT NULL, error_type TEXT);
                CREATE TABLE IF NOT EXISTS controls(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT OR IGNORE INTO controls VALUES('disabled','false');
                PRAGMA user_version=1;
            ''')
        # Registry reconstruction is metadata-only, but stale ACTIVE snapshots
        # are immediately quarantined rather than advertised after restart.
        with self.connect() as db:active=[r[0] for r in db.execute("SELECT id FROM skills WHERE state='ACTIVE'")]
        for identifier in active:
            try:self.fresh(self.get(identifier))
            except (ValueError,OSError,KeyError,TypeError):self.transition(identifier,'QUARANTINED')

    def connect(self):
        if linked(self.path):raise ValueError('Linked registry database refused.')
        db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON');return db

    def require_enabled(self):
        if not self.enabled:raise ValueError('Repository skills are disabled in configuration.')
        with self.connect() as db:
            if db.execute("SELECT value FROM controls WHERE key='disabled'").fetchone()[0]!='false':
                raise ValueError('All repository skills are emergency-disabled.')

    def note(self,kind,identifier):
        self.report('brain','Repository skills: '+kind+' '+identifier)
        if self.memory is not None:self.memory.record('repository_skill',kind+' '+identifier)

    def learn(self,target,cancelled=lambda:False):
        self.require_enabled()
        with self.learning:
            self.report('brain','Inspecting repository as untrusted source; no imports or dependency installation.')
            canonical,local=identity(target);snapshot=None
            if local is None:
                repo_id=hashlib.sha256(canonical.encode()).hexdigest()[:20]
                with self.connect() as db:
                    retained=db.execute('SELECT v.snapshot FROM revisions v JOIN repositories r ON r.id=v.repo_id AND r.current_revision=v.revision WHERE r.id=?',(repo_id,)).fetchone()
                if retained:
                    known=json.loads(retained[0]);remote=git(['ls-remote','--',canonical,'HEAD'],cancelled,20).decode().split()
                    if remote and remote[0]==known['commit']:
                        verify_snapshot(known,self.vault);snapshot=known
            if snapshot is None:snapshot=acquire(target,self.vault,cancelled)
            root=verify_snapshot(snapshot,self.vault)
            with self.connect() as db:
                found=db.execute('SELECT knowledge FROM revisions WHERE repo_id=? AND revision=?',(snapshot['repo_id'],snapshot['revision'])).fetchone()
            knowledge=json.loads(found[0]) if found else None
            reanalyzed=bool(knowledge and knowledge.get('analysis_version')!=2)
            if knowledge is None or reanalyzed:knowledge=analyze(root,cancelled)
            if not knowledge['entities']:raise ValueError('No public callable Python candidates; diagnostics: '+json.dumps(knowledge['diagnostics'])[:500])
            with self.connect() as db:
                existing=db.execute('SELECT current_revision FROM repositories WHERE id=?',(snapshot['repo_id'],)).fetchone()
                if existing and existing[0]!=snapshot['revision']:
                    db.execute("UPDATE skills SET state='DISABLED',approved=0 WHERE repo_id=?",(snapshot['repo_id'],))
                db.execute('INSERT INTO repositories VALUES(?,?,?,0) ON CONFLICT(id) DO UPDATE SET current_revision=excluded.current_revision',
                           (snapshot['repo_id'],snapshot['identity'],snapshot['revision']))
                db.execute('INSERT OR IGNORE INTO revisions VALUES(?,?,?,?,?)',
                    (snapshot['repo_id'],snapshot['revision'],json.dumps(snapshot),json.dumps(knowledge),now()))
                if reanalyzed:
                    db.execute('UPDATE revisions SET knowledge=? WHERE repo_id=? AND revision=?',(json.dumps(knowledge),snapshot['repo_id'],snapshot['revision']))
                for entity in knowledge['entities']:
                    name='rs_'+snapshot['repo_id'][:10]+'_'+hashlib.sha256((snapshot['revision']+entity['module']+'.'+entity['symbol']).encode()).hexdigest()[:24]
                    state='ANALYZED' if entity['supported'] else 'QUARANTINED'
                    db.execute('INSERT OR IGNORE INTO skills(id,repo_id,revision,entity,state,updated) VALUES(?,?,?,?,?,?)',
                               (name,snapshot['repo_id'],snapshot['revision'],json.dumps(entity),state,now()))
                    if reanalyzed:
                        db.execute("UPDATE skills SET entity=?,state=CASE WHEN state IN ('REVOKED','DISABLED') THEN state ELSE ? END,approved=0,validation=NULL,updated=? WHERE id=?",(json.dumps(entity),state,now(),name))
            self.note('analyzed',snapshot['repo_id'])
            with self.connect() as db:
                active=db.execute("SELECT count(*) FROM skills WHERE repo_id=? AND revision=? AND state='ACTIVE' AND approved=1",(snapshot['repo_id'],snapshot['revision'])).fetchone()[0]
            return {'repo_id':snapshot['repo_id'],'identity':snapshot['identity'],'commit':snapshot['commit'],'revision':snapshot['revision'],
                'files_scanned':knowledge['files_scanned'],'candidates':len(knowledge['entities']),
                'supported_candidates':sum(e['supported'] for e in knowledge['entities']),
                'diagnostics':snapshot['diagnostics']+knowledge['diagnostics'],'active_skills':active,
                'status':'Static discovery only; candidates require approved isolated smoke validation and explicit activation.'}

    def get(self,identifier):
        if not re.fullmatch(r'rs_[a-f0-9]{10}_[a-f0-9]{24}',identifier):raise ValueError('Invalid repository skill identifier.')
        with self.connect() as db:
            row=db.execute('SELECT s.*,r.current_revision,r.disabled,v.snapshot FROM skills s JOIN repositories r ON r.id=s.repo_id JOIN revisions v ON v.repo_id=s.repo_id AND v.revision=s.revision WHERE s.id=?',(identifier,)).fetchone()
        if not row:raise ValueError('Unknown repository-derived skill.')
        data=dict(row);data['entity']=json.loads(data['entity']);data['snapshot']=json.loads(data['snapshot'])
        data['validation']=json.loads(data['validation']) if data['validation'] else None
        entity=data['entity']
        if data['state'] not in STATES or not isinstance(entity.get('schema'),dict):raise ValueError('Corrupted skill manifest; execution refused.')
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',entity.get('module','')) or not re.fullmatch(r'[A-Za-z]\w*(?:\.[A-Za-z]\w*)?',entity.get('symbol','')):
            raise ValueError('Invalid stored module/symbol; execution refused.')
        if entity.get('kind') not in {'function','method','static_method','class_method'}:raise ValueError('Unsupported stored callable kind.')
        root=Path(entity.get('import_root',''))
        if root.is_absolute() or '..' in root.parts or entity.get('import_root') not in {'.','src'}:raise ValueError('Unsafe stored import root.')
        expected='rs_'+data['repo_id'][:10]+'_'+hashlib.sha256((data['revision']+entity['module']+'.'+entity['symbol']).encode()).hexdigest()[:24]
        if expected!=identifier:raise ValueError('Skill identity does not match its pinned target.')
        return data

    def transition(self,identifier,state,approved=0,validation=None):
        if state not in STATES:raise ValueError('Invalid lifecycle state.')
        with self.connect() as db:
            db.execute('UPDATE skills SET state=?,approved=?,validation=COALESCE(?,validation),updated=? WHERE id=?',
                (state,approved,json.dumps(validation) if validation is not None else None,now(),identifier))

    def fresh(self,skill):
        try:return verify_snapshot(skill['snapshot'],self.vault)
        except (ValueError,OSError,KeyError) as error:
            self.transition(skill['id'],'QUARANTINED');raise ValueError('Source integrity failed; skill quarantined: '+str(error)) from error

    def check(self,identifier,arguments,approve,cancelled=lambda:False):
        self.require_enabled();skill=self.get(identifier)
        if not skill['entity']['supported'] or skill['state']=='REVOKED':raise ValueError('Capability requires an explicit adapter or is revoked.')
        validate(skill['entity']['schema'],arguments)
        root=self.fresh(skill)
        status=self.runtime.status(refresh=True)
        if not status['available']:raise ValueError('Validation blocked by isolation: '+status['reason'])
        approve('repository_skill_validation',json.dumps({'skill':identifier,'module':skill['entity']['module'],'symbol':skill['entity']['symbol'],'commit':skill['snapshot']['commit'],'image':status['image_id'],'arguments':arguments,'network':'none','files':'snapshot read-only; ephemeral scratch'}),cancelled)
        try:
            value,image=self.runtime.run(root,{'entity':skill['entity'],'arguments':arguments},cancelled)
            self.fresh(skill)
            validation={'passed':True,'at':now(),'image_id':image,'runner_hash':status.get('runner_hash'),'revision':skill['revision'],'arguments_hash':hashlib.sha256(json.dumps(arguments,sort_keys=True).encode()).hexdigest()}
            self.transition(identifier,'VALIDATED',validation=validation);self.note('validated',identifier)
            return {'skill':identifier,'state':'VALIDATED','value':value,'validation':validation}
        except Exception as error:
            self.transition(identifier,'QUARANTINED',validation={'passed':False,'at':now(),'error_type':type(error).__name__})
            raise

    def activate(self,identifier,approve,cancelled=lambda:False):
        self.require_enabled();skill=self.get(identifier);validation=skill['validation']
        if skill['state']!='VALIDATED' or not validation or validation.get('passed') is not True:raise ValueError('Activation requires fresh successful isolated smoke validation.')
        if skill['disabled'] or skill['revision']!=skill['current_revision']:raise ValueError('Repository is disabled or this version is not current.')
        self.fresh(skill);runtime=self.runtime.status(refresh=True)
        if not runtime['available'] or runtime['image_id']!=validation.get('image_id') or runtime.get('runner_hash')!=validation.get('runner_hash'):raise ValueError('Validated runtime changed or is unavailable; revalidate.')
        approve('repository_skill_activation',json.dumps({'skill':identifier,'revision':skill['revision'],'risk':'Untrusted repository code; JSON-only isolated execution; approval required for each call.'}),cancelled)
        if cancelled():raise ValueError('Activation cancelled.')
        self.transition(identifier,'ACTIVE',approved=1);self.note('active',identifier)
        return {'skill':identifier,'state':'ACTIVE','hot_loaded':True,'host_imported':False}

    def invoke(self,identifier,arguments,approve,cancelled=lambda:False):
        self.require_enabled();skill=self.get(identifier)
        if skill['state']!='ACTIVE' or not skill['approved'] or skill['disabled'] or skill['revision']!=skill['current_revision']:
            raise ValueError('Repository skill is not active/approved for the current version.')
        validate(skill['entity']['schema'],arguments);root=self.fresh(skill)
        status=self.runtime.status(refresh=True)
        if not status['available']:raise ValueError('Execution blocked by isolation: '+status['reason'])
        if not skill['validation'] or skill['validation'].get('passed') is not True or status['image_id']!=skill['validation'].get('image_id') or status.get('runner_hash')!=skill['validation'].get('runner_hash'):
            self.transition(identifier,'QUARANTINED');raise ValueError('Runtime or validation changed; isolated validation required.')
        approve('repository_skill_execution',json.dumps({'skill':identifier,'arguments':arguments,'revision':skill['revision'],'network':'none','filesystem':'snapshot read-only; ephemeral scratch'}),cancelled)
        outcome='failed'
        try:
            # Recheck source and lifecycle after a potentially long approval dialog.
            current=self.get(identifier)
            if current['state']!='ACTIVE' or not current['approved'] or current['disabled']:raise ValueError('Skill authorization changed before execution.')
            self.require_enabled();root=self.fresh(current)
            def stopped():
                if cancelled():return True
                try:
                    self.require_enabled();latest=self.get(identifier)
                    return latest['state']!='ACTIVE' or not latest['approved'] or latest['disabled'] or latest['revision']!=latest['current_revision']
                except (ValueError,sqlite3.Error):return True
            value,image=self.runtime.run(root,{'entity':current['entity'],'arguments':arguments},stopped)
            self.fresh(current);outcome='success';return {'skill':identifier,'value':value,'image_id':image,'source_revision':current['revision']}
        except Exception:
            with self.connect() as db:
                db.execute("UPDATE skills SET state='FAILED',approved=0,updated=? WHERE id=? AND state='ACTIVE'",(now(),identifier))
            raise
        finally:
            with self.connect() as db:db.execute('INSERT INTO outcomes(skill_id,at,outcome) VALUES(?,?,?)',(identifier,now(),outcome))
            self.note(outcome,identifier)

    def search(self,query='.',limit=12,active_only=False):
        if not self.enabled:return []
        limit=max(1,min(int(limit),30));tokens=words(query)
        with self.connect() as db:
            if db.execute("SELECT value FROM controls WHERE key='disabled'").fetchone()[0]!='false':return []
            rows=db.execute('SELECT s.id,s.entity,s.state,s.repo_id,s.revision,s.approved,r.identity,r.disabled,r.current_revision FROM skills s JOIN repositories r ON r.id=s.repo_id ORDER BY s.id LIMIT 10000').fetchall()
        matches=[]
        for row in rows:
            if active_only and (row['state']!='ACTIVE' or not row['approved'] or row['disabled'] or row['revision']!=row['current_revision']):continue
            entity=json.loads(row['entity']);score=len(tokens & words(row['identity']+' '+entity['module']+' '+entity['symbol']))
            if query=='.' or not tokens or score or query in {row['id'],row['repo_id']}:
                item={'id':row['id'],'repo_id':row['repo_id'],'identity':row['identity'],'state':row['state'],'module':entity['module'],'symbol':entity['symbol'],
                    'async':entity['async'],'schema':entity['schema'],'description':entity['description'],'rejection':entity['rejection']}
                matches.append((score,item))
        matches.sort(key=lambda r:(-r[0],r[1]['id']))
        return [item for _,item in matches[:limit]]

    def lifecycle(self,target,operation,approve,cancelled=lambda:False,revision=None):
        if operation not in {'disable','revoke','disable_repository','disable_all','enable_all','rollback','enable_repository'}:raise ValueError('Unsupported skill lifecycle operation.')
        if operation in {'rollback','enable_all','enable_repository'}:
            approve('repository_skill_lifecycle',json.dumps({'target':target,'operation':operation,'revision':revision}),cancelled)
        if cancelled():raise ValueError('Lifecycle action cancelled.')
        with self.connect() as db:
            if operation in {'disable_all','enable_all'}:db.execute("UPDATE controls SET value=? WHERE key='disabled'",('true' if operation=='disable_all' else 'false',))
            elif operation in {'disable_repository','enable_repository'}:
                if not db.execute('SELECT 1 FROM repositories WHERE id=?',(target,)).fetchone():raise ValueError('Unknown repository identifier.')
                db.execute('UPDATE repositories SET disabled=? WHERE id=?',(1 if operation=='disable_repository' else 0,target))
                if operation=='disable_repository':db.execute("UPDATE skills SET state='DISABLED',approved=0 WHERE repo_id=?",(target,))
            elif operation=='rollback':
                row=db.execute('SELECT snapshot FROM revisions WHERE repo_id=? AND revision=?',(target,revision)).fetchone()
                if not row:raise ValueError('Unknown retained repository revision.')
                verify_snapshot(json.loads(row[0]),self.vault)
                db.execute('UPDATE repositories SET current_revision=? WHERE id=?',(revision,target))
                db.execute("UPDATE skills SET state='DISABLED',approved=0 WHERE repo_id=?",(target,))
            else:
                self.get(target);db.execute('UPDATE skills SET state=?,approved=0 WHERE id=?',('REVOKED' if operation=='revoke' else 'DISABLED',target))
        self.note(operation,target)
        return {'target':target,'operation':operation,'retained_source':True,'requires_revalidation_to_activate':True}

    def health(self):
        with self.connect() as db:
            counts={row[0]:row[1] for row in db.execute('SELECT state,count(*) FROM skills GROUP BY state')}
            repos=db.execute('SELECT count(*) FROM repositories').fetchone()[0]
        return {'enabled':self.enabled,'repositories':repos,'states':counts,'isolation':self.runtime.status(),'host_imports':False}


def engine(actions):
    current=getattr(actions,'repository_skills',None)
    if not isinstance(current,RepositorySkills):
        config=getattr(actions,'config',{})
        config=config if isinstance(config,dict) else {}
        current=RepositorySkills(actions.base,config.get('repository_skills'),
            getattr(actions,'memory',None),getattr(actions,'report',lambda *args:None))
        actions.repository_skills=current
        memory=getattr(actions,'memory',None)
        if memory is not None:memory.repository_skills=current
    return current
