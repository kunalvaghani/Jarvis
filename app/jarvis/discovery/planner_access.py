"""Typed proposals from the existing planner into the existing brain dispatcher.

This module never plans, calls a model, grants approval or supplies case answers.
Model-authored inputs remain explicitly unverified assumptions in unified memory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import uuid

from .catalog import enabled

DESCRIPTION = ('Use existing scientific Lab workflows. value=help for commands and input schemas; '
    'otherwise value is one supported lab command. content is optional JSON object authored by you; '
    'use a quoted "{request}" placeholder where the command needs an input file. '
    'The runtime saves this as unverified proposed assumptions, never measured facts. '
    'Existing resource, permission, approval and independent verification gates apply. '
    'A workflow pass is conditional numerical evidence, not full project or physical validation.')


def _render_result(result):
    # Journal canonicalization sorts keys. Restore the bounded source index to
    # the beginning on readback too; reuse must not hide it behind verbose answer.
    if isinstance(result.get('source_summary'),dict):
        summary=result['source_summary']
        summary={**{key:summary[key] for key in ('source_refs','query','content_is_untrusted','verification_scope') if key in summary},**summary}
        result={**result,'source_summary':summary}
        result={'source_summary':summary,**result}
    return json.dumps(result,ensure_ascii=False)


def _payload(content):
    if not isinstance(content, str) or len(content.encode('utf-8')) > 10000:
        raise ValueError('Lab request must be at most 10000 UTF-8 bytes')
    if not content.strip():
        return None
    def reject(value):
        raise ValueError('Nonfinite scientific input is forbidden')
    data = json.loads(content, parse_constant=reject)
    if not isinstance(data, dict):
        raise ValueError('Lab request must be a JSON object')
    from ..tools import APPROVAL_CLAIMS
    def inspect(value, depth=0):
        if depth > 20:
            raise ValueError('Lab request nesting exceeds its bound')
        if isinstance(value, dict):
            for key, item in value.items():
                if key.casefold() in APPROVAL_CLAIMS:
                    raise ValueError('A model proposal cannot grant authorization')
                inspect(item, depth+1)
        elif isinstance(value, list):
            for item in value:
                inspect(item, depth+1)
    inspect(data)
    return data


def help_report(domain=None,config=None):
    from .model.pendulum import Pendulum
    from .model.optimization import Study
    from .model.relativity import ClockCase
    from .model.mechanics import MechanicsCase
    from .model.vehicle import VehicleCase
    schemas={'pendulum':Pendulum,'study':Study,'dilation':ClockCase,'mechanics':MechanicsCase,'vehicle':VehicleCase}
    active=list(schemas) if config is None else ([name for name in schemas if
        (enabled(config,'sim') and (name!='dilation' or enabled(config,'research')))])
    if domain is not None:
        if domain not in active:raise ValueError('This schema family is disabled in the current session')
        commands={'mechanics':'lab simulate mechanics "{request}"','pendulum':'lab simulate pendulum "{request}"',
                  'study':'lab optimize "{request}"','dilation':'lab theory dilation "{request}"',
                  'vehicle':'lab compare vehicle "{request}"'}
        result={'domain':domain,'schema':schemas[domain].model_json_schema(),
                'native_transport':{'operation':'run','command':commands[domain],
                    'request':'Supply a JSON object matching schema, with your explicit assumptions.',
                    'expected':'Supply a short description of the expected conditional result.'},
                'origin':'proposed assumptions require independent provenance checks'}
        if domain=='mechanics':
            from .adapters.mechanics import qualification
            result['runtime']=qualification()
            result['model_limits']=['primitive rigid bodies at rest initially','no contact or fluid drag',
                'no actuator, material-strength or field model','conditional simulation; not physical validation']
        if domain=='vehicle':
            from .vehicle_wire import schema
            result['schema']=schema()
            result['schema_note']='Compact grouped SI vectors reduce reply size. Every number is explicit; missing numbers are rejected. Existing full VehicleCase SI files remain accepted.'
            from .adapters.chrono import qualification
            result['runtime']=qualification()
            result['model_limits']=['Assumed parametric double-wishbone topology, not proprietary F1 internals.',
                'Aero coefficient/slope surrogate, not CFD. No measured tire calibration.',
                'Prescribed controls on flat terrain; maximum observed speed is not verified terminal top speed.',
                'Mechanical engine energy is not fuel/battery energy; full Test A needs separate source/native-visual/track audit.',
                'source_refs must be actual hashed Source IDs in unified memory, not invented URLs.']
        return result
    commands=['lab status']
    if config is None or enabled(config,'sim'):commands += ['lab convert <number> <unit> to <unit>',
        'lab simulate divider <volts> V <upper> ohm <lower> ohm',
        'lab simulate pendulum "{request}"', 'lab build pendulum "{request}"',
        'lab simulate mechanics "{request}"',
        'lab compare vehicle "{request}"',
        'lab optimize "{request}"',
        'lab optimize step "<study ID>"', 'lab optimize status "<study ID>"',
        'lab optimize pause "<study ID>"', 'lab optimize resume "<study ID>"']
    if config is None or enabled(config,'research'):commands += ['lab research "<public question>"','lab lookup doi "<DOI>"',
        'lab assets search "<exact variant/year and object query>"', 'lab assets inspect "<model UID from source results>"']
    commands += ['lab background "<public source query>"','lab portal read "<public URL>"',
                 'lab inspect asset "{request}"','lab inspect project "{request}"']
    if 'dilation' in active:commands += ['lab theory dilation "{request}"']
    return {'commands':commands,
        'schema_names':active,'schema_access':'Use native operation=help, topic=<schema name> to inspect one schema.',
        'limits': 'Only registered, enabled workflows run. Unsupported science remains unmet. '
                  'No model-supplied source or numerical property is independently established by submission.'}


def execute(actions, command, content, cancelled):
    config = getattr(actions, 'config', {})
    if not enabled(config):
        raise ValueError('The scientific Lab is disabled')
    if cancelled():
        raise ValueError('Lab proposal cancelled before dispatch')
    if not isinstance(command, str) or len(command) > 1000:
        raise ValueError('A bounded Lab command is required')
    data = _payload(content)
    help_match=re.fullmatch(r'help(?: (pendulum|study|dilation|mechanics|vehicle))?',command)
    if help_match:
        if data is not None:
            raise ValueError('Lab help accepts no request body')
        return json.dumps(help_report(help_match[1],config), ensure_ascii=False)
    if not re.match(r'^lab\s+', command, re.I) or '\n' in command or '\r' in command:
        raise ValueError('Only registered Lab commands may be delegated')
    if (data is not None) != (command.count('{request}') == 1) or command.count('{request}') > 1:
        raise ValueError('A request object requires exactly one quoted {request} placeholder')
    if data is not None and '"{request}"' not in command:
        raise ValueError('Quote the request placeholder')
    from ..neural.service import service_for, approver
    from ..neural.compiler import compile_goal
    from ..neural.dispatcher import Env
    service = service_for(actions)
    if service is None:
        raise ValueError('Existing neural brain service required for Lab execution')
    plan = compile_goal(command, service.journal, config, service.graph.version)
    if plan is None or not plan.workflow.startswith('discovery.'):
        raise ValueError('No enabled Lab workflow matches this command')
    from ..task_state import TaskState
    state = getattr(actions, 'task_state', None)
    task_id = state.running_identity() if isinstance(state, TaskState) else None
    # Calls outside a durable task remain API checks, never autonomous acceptance.
    scope = task_id or ('api-' + uuid.uuid4().hex)
    canonical = json.dumps({'command':command, 'request':data}, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    key = hashlib.sha256((scope+':'+digest).encode()).hexdigest()
    journal = service.journal
    proposal_ref = journal.put({'proposal':json.loads(canonical), 'origin':'model_proposed_unverified',
                                'task_id':task_id}, 'Report')  # Secret guard before any request file.
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_planner_calls '
                   '(id TEXT PRIMARY KEY, graph_version INTEGER, state TEXT, goal_id TEXT, result_ref TEXT, proposal_ref TEXT)')
        old = db.execute('SELECT * FROM discovery_planner_calls WHERE id=?', (key,)).fetchone()
        if old is None:
            db.execute('INSERT INTO discovery_planner_calls VALUES (?,?,?,?,?,?)',
                       (key, service.graph.version, 'pending', plan.goal_id, None, proposal_ref))
    if old is not None:
        # sqlite returns tuples here; Journal.rows normalizes separately.
        row = journal.rows('SELECT * FROM discovery_planner_calls WHERE id=?', (key,))[0]
        if row['state'] == 'done' and row['graph_version'] == service.graph.version:
            return _render_result(json.loads(journal.get(row['result_ref'])))
        raise ValueError('Prior Lab call is incomplete, failed or changed; inspect its journal before any new action')
    try:
        if data is not None:
            from ..skill_memory import linked
            root = Path(actions.base).resolve()
            directory = root / '.jarvis-runtime/discovery/requests'
            if any(linked(p) for p in (directory, *directory.parents) if p.is_relative_to(root)):
                raise ValueError('Linked request directory refused')
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (digest+'.json')
            body = json.dumps(data, sort_keys=True, allow_nan=False).encode('utf-8')
            if path.exists():
                if linked(path) or path.read_bytes() != body:
                    raise ValueError('Request artifact changed; overwrite refused')
            else:
                with path.open('xb') as stream:
                    stream.write(body)
            from .contracts import Source
            from .memory import LabMemory
            memory = LabMemory(journal); memory.migrate()
            relative = path.relative_to(root).as_posix()
            memory.put(Source(id='proposal-'+digest, locator=relative,
                sha256=hashlib.sha256(body).hexdigest(), author='Jarvis planner proposal',
                justification='Model-proposed unverified assumptions; source assertions require independent corroboration.'))
            command = command.replace('{request}', relative)
            plan = compile_goal(command, journal, config, service.graph.version)
            if plan is None or not plan.workflow.startswith('discovery.'):
                raise ValueError('Materialized request no longer fits a Lab workflow')
            with journal.tx() as db:
                db.execute('UPDATE discovery_planner_calls SET goal_id=? WHERE id=?', (plan.goal_id,key))
        if task_id:
            state.require_identity(task_id)
        outcome = service.dispatcher.run(plan, Env(actions=actions, cancelled=cancelled,
            approve=approver(actions, cancelled), config=config))
        result = {'goal_id':outcome.goal_id, 'state':outcome.state, 'verified':outcome.verified,
            'answer':outcome.answer, 'stop_reason':outcome.stop_reason,
            'proposal_ref':proposal_ref, 'input_origin':'model_proposed_unverified',
            'physical_validation':False, 'autonomous_task_id':task_id}
        if outcome.verified and plan.workflow=='discovery.assets.search_public':
            # Put actual source IDs/candidate names ahead of verbose descriptions
            # so ordinary tool-result clipping does not hide relevant records.
            # This is a projection of verified output, never a chosen asset or
            # a promotion of the provider's engineering/license assertions.
            from .acceptance import artifact
            from .asset_preflight import context
            rows=journal.rows('SELECT result_ref FROM outbox WHERE goal_id=? AND node_id=? AND state=?',
                (outcome.goal_id,'discovery.assets.search_public@v1','done'))
            if len(rows)!=1:raise ValueError('Verified source producer receipt missing')
            source=artifact(journal,artifact(journal,rows[0]['result_ref'])['report'])['result']
            summary=context({'verified':True,'result':json.dumps({**source,'goal_id':outcome.goal_id})})
            result={'source_summary':summary,**result}
        ref = journal.put(result,'Report')
        with journal.tx() as db:
            db.execute('UPDATE discovery_planner_calls SET state=?,result_ref=? WHERE id=?',
                       ('done' if outcome.verified else 'failed',ref,key))
        if not outcome.verified:
            raise ValueError('Lab workflow stopped: '+outcome.state+'; '+outcome.stop_reason)
        return _render_result(result)
    except BaseException:
        with journal.tx() as db:
            db.execute("UPDATE discovery_planner_calls SET state='uncertain' WHERE id=? AND state='pending'",(key,))
        raise
