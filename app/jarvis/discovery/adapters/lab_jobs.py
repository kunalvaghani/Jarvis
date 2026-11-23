"""Scoped controls over existing C4 studies and ScheduledQueue; no runner or mail sender."""
from ..model.optimization import Studies,enqueue_remaining

def operate(journal,actions,config,operation,study_id):
    from ...task_scheduler import ScheduledQueue
    queue=getattr(actions,'queue',None)
    if type(queue) is not ScheduledQueue:raise ValueError('existing durable queue required; no service is started')
    studies=Studies(journal);studies.load(study_id,actions.base)
    with journal.tx() as db:db.execute('CREATE TABLE IF NOT EXISTS discovery_job_tasks (study TEXT NOT NULL,task_id TEXT NOT NULL,PRIMARY KEY(study,task_id))')
    rows=journal.rows('SELECT task_id FROM discovery_job_tasks WHERE study=?',(study_id,));ids=[r['task_id'] for r in rows]
    if operation=='queue':
        ids=enqueue_remaining(studies,queue,config,study_id,getattr(actions,'generation',0))
        with journal.tx() as db:
            for identity in ids:db.execute('INSERT OR IGNORE INTO discovery_job_tasks VALUES (?,?)',(study_id,identity))
    elif operation in ('pause','resume','cancel'):
        # Preflight resume before changing study state. Started tasks require the
        # existing explicit reconciliation flow; no uncertain job is replayed.
        if operation=='resume':
            for identity in ids:
                row=queue.store.get(identity)
                if row and row['state']=='PAUSED' and (row['checkpoint'].get('uncertain') or row['checkpoint'].get('dispatch_at')):
                    raise ValueError('started job needs existing task reconciliation; no automatic replay')
        studies.control(study_id,operation)
        for identity in ids:queue.control(operation,identity)
    elif operation!='status':raise ValueError('unknown scoped job operation')
    report=studies.describe(study_id);states={}
    for row in journal.rows('SELECT task_id FROM discovery_job_tasks WHERE study=?',(study_id,)):
        task=queue.store.get(row['task_id'])
        if not task or task['command']['value']!='lab optimize step "'+study_id+'"':raise ValueError('owned job binding changed')
        states[task['state']]=states.get(task['state'],0)+1
    return {'study_id':study_id,'study_state':report['state'],'task_counts':states,'objective_met':report['objective_met'],
        'scenario_sha256':report['scenario_sha256'],'global_queue_controls_unchanged':True,'emails_sent':0}
