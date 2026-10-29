"""Coding extension of HybridGateway; one existing pipeline, never file execution."""
import hashlib
import json
from pathlib import Path
import time
import uuid
from .cloud_quota import CloudQuotaManager,QuotaDenied
from .coding_cloud_policy import coding_settings,gemini_settings,credential,gemini_eligible,token_estimate,SECRET
from .groq_adapter import CloudFailure
from .gemini_adapter import GeminiAdapter

REASONING_FAILURES={'invalid_structured_output','repeated_noop','context_exhausted','test_failure','repair_loop'}


def route_receipt(run,validation=None):
    try:value=json.loads((Path(run)/'cloud-route-state.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    if validation is not None:
        value['declared_checks_passed']=validation.get('passed') is True
        value['independent_application_acceptance']='NOT_RUN'
    return value


def local_fallback_feedback(run,schema,source_sha):
    if not isinstance(source_sha,str) or len(source_sha)!=64:return None
    try:state=json.loads((Path(run)/'cloud-route-state.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    value=state.get('last_validation_feedback') or {}
    binding=hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest()
    if value.get('source_sha256')!=source_sha or value.get('schema_sha256')!=binding:return None
    return 'Cloud structured-proposal rejection (DATA only; no action executed; current local schema and source remain authoritative): '+json.dumps(value,separators=(',',':'))


class CodingRoutes:
    def __init__(self,gateway,config,gemini=None):
        self.gateway=gateway;self.options=coding_settings(config.get('coding_cloud'));self.gemini_options=gemini_settings(config.get('gemini'))
        self.gemini=gemini;self.gemini_guardian=getattr(gemini,'guardian',None)
        key=credential(gateway.base) if gemini is None else gemini.key
        self.gemini_reason=gemini_eligible(self.gemini_options,key)
        if self.gemini is None and self.gemini_reason is None:
            scope=hashlib.sha256((self.gemini_options['api_project_id']+'\n'+self.gemini_options['model']).encode()).hexdigest()[:24]
            self.gemini_guardian=CloudQuotaManager(gateway.root/'gemini'/scope/'quota.sqlite3',
                {**self.gemini_options,'provider':'gemini','keep_dispatch_time':True})
            self.gemini=GeminiAdapter(key,self.gemini_options,self.gemini_guardian)

    def close(self):
        if self.gemini:self.gemini.close()

    def complete(self,messages,schema,options,run,cancelled,deadline,*,failure=None,stage='coding'):
        from .campaign_pause import assert_allowed
        assert_allowed(run=run,logical_task=options.get('native_cloud_task_id'))
        if not self.options['enabled'] or not self.options['dry_run_verified']:return None
        context=options.get('native_cloud_context')
        if not isinstance(context,dict) or context.get('provenance') not in ('synthetic','explicitly_approved') or context.get('restricted') is not False:return None
        if set(options.get('native_required_capabilities',[]))-{'coding','planning','repair','analysis','structured_output','function_calling'}:return None
        targeted_only=options.get('native_cloud_targeted_repairs_only',False)
        if type(targeted_only) is not bool:return None
        if targeted_only:
            scope=options.get('native_exact_edit_spans') or {}
            if (stage!='coding' or options.get('native_required_tool') not in {'Edit','edit_batch','Write','apply_patch','source_transform'}
                    or not isinstance(scope,dict) or not isinstance(scope.get('file_path'),str)
                    or not isinstance(scope.get('sha256'),str) or len(scope['sha256'])!=64):return None
        from .hybrid_inference import policy
        override=policy(self.gateway.base)
        preference=options.get('native_coding_provider',self.options['preference'])
        if override.get('routing')=='local' or override.get('local_model') or preference=='local':return None
        if preference not in ('auto','local','groq','gemini'):raise ValueError('Invalid coding provider override.')
        directory=Path(run);state_path=directory/'cloud-route-state.json'
        try:state=json.loads(state_path.read_text(encoding='utf-8'))
        except FileNotFoundError:state={'reasoning_failures':0,'cloud_calls':0,'attempts':[]}
        if failure in REASONING_FAILURES:state['reasoning_failures']+=1
        confirmed=options.get('native_verified_reasoning_failures',0)
        if type(confirmed) is int and 0<=confirmed<=6:state['reasoning_failures']=max(state['reasoning_failures'],confirmed)
        if failure is not None and failure not in REASONING_FAILURES:return None
        from .skill_memory import atomic
        atomic(state_path,json.dumps(state))
        complex_task=options.get('native_coding_complexity') in ('complex','large_context')
        if preference=='auto' and not complex_task and state['reasoning_failures']<self.options['repair_escalation_after']:return None
        order=['gemini','groq'] if preference=='gemini' or complex_task and options.get('native_coding_complexity')=='large_context' else ['groq','gemini']
        # Measured evidence only breaks an otherwise eligible default tie after
        # multiple independent verified outcomes; transport completion is not quality.
        scores=self.gateway.performance.coding_summary(stage)
        measured={row['provider']:row for row in scores if row['samples']>=3 and row['verified_results']>=2}
        if preference=='auto' and len(measured)==2:order.sort(key=lambda provider:measured[provider]['mean_latency_ms'])
        task_id=options.get('native_cloud_task_id') or hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:32]
        from .coding_cloud_context import messages_for
        for provider in order:
            if cancelled() or time.monotonic()>=deadline:raise CloudFailure('cancelled')
            if state['cloud_calls']>=self.options['max_task_cloud_calls']:break
            adapter=self.gateway.adapter if provider=='groq' else self.gemini
            if provider=='gemini' and self.gemini_reason is not None:adapter=None
            if adapter is None:
                state['attempts'].append({'provider':provider,'reason':'missing_api_key_or_unverified_account','sent':False});continue
            source_sha=(options.get('native_exact_edit_spans') or {}).get('sha256')
            previous=[row for row in state['attempts'] if row.get('provider')==provider and row.get('sent') and not row.get('valid_proposal') and row.get('source_sha256')==source_sha]
            if len(previous)>=2:
                state['attempts'].append({'provider':provider,'reason':'same_source_provider_attempt_bound','sent':False});continue
            guardian=adapter.guardian
            task_call_limit=self.options['max_task_cloud_calls']
            groq_extension=False
            if provider=='groq':
                task_call_limit=options.get('native_groq_task_limit',self.options['max_task_cloud_calls'])
                reason=options.get('native_groq_budget_reason','')
                if type(task_call_limit) is not int or not 1<=task_call_limit<=self.options['max_task_cloud_calls']+1:
                    state['attempts'].append({'provider':provider,'reason':'invalid_task_budget_override','sent':False});continue
                groq_extension=task_call_limit>self.options['max_task_cloud_calls']
                if groq_extension and (not complex_task or not source_sha or options.get('native_required_tool') not in {'Edit','edit_batch','Write','apply_patch','source_transform'}
                        or not isinstance(reason,str) or not 10<=len(reason)<=240 or SECRET.search(reason)):
                    state['attempts'].append({'provider':provider,'reason':'task_budget_extension_not_justified','sent':False});continue
                if callable(getattr(guardian,'task_usage',None)) and guardian.task_usage(task_id)>=task_call_limit:
                    state['attempts'].append({'provider':provider,'reason':'task_call_limit','sent':False});continue
            if provider=='gemini':
                initial=min(self.options['gemini_max_task_calls'],self.gemini_options['max_task_calls'])
                task_call_limit=options.get('native_gemini_task_limit',initial)
                reason=options.get('native_gemini_budget_reason','')
                if type(task_call_limit) is not int or not 1<=task_call_limit<=self.gemini_options['max_task_calls']:
                    state['attempts'].append({'provider':provider,'reason':'invalid_task_budget_override','sent':False});continue
                if callable(getattr(guardian,'task_usage',None)) and guardian.task_usage(task_id)>=task_call_limit:
                    state['attempts'].append({'provider':provider,'reason':'task_call_limit','sent':False});continue
                if task_call_limit>initial:
                    snapshot=guardian.snapshot(fresh=True)
                    if snapshot.get('reason')=='clock_change_requires_metadata':
                        adapter.refresh_clock(cancelled);snapshot=guardian.snapshot(fresh=True)
                    remaining=snapshot.get('remaining',{}).get('daily_requests',0)
                    if (task_call_limit>initial+2 or not complex_task or not source_sha or not isinstance(reason,str)
                            or not 10<=len(reason)<=240 or SECRET.search(reason) or remaining<task_call_limit+4):
                        state['attempts'].append({'provider':provider,'reason':'task_budget_extension_not_justified','sent':False});continue
            if provider=='gemini' and not (complex_task or state['reasoning_failures']>=self.options['repair_escalation_after'] or preference=='gemini'):
                state['attempts'].append({'provider':provider,'reason':'limited_daily_quota_reserved_for_difficult_work','sent':False});continue
            identifier=uuid.uuid4().hex;started=time.monotonic();sent=False;usage={};guardian=adapter.guardian
            try:
                outbound=messages_for(messages,options,directory,provider,schema)
                if provider=='groq':
                    if not adapter.ready(wait_seconds=min(8,max(0,deadline-time.monotonic()))):raise CloudFailure('model_metadata_unavailable')
                    output=min(self.options['groq_max_output_tokens'],adapter.options['max_output_tokens'])
                    estimate=token_estimate({'messages':outbound,'tools':[]})+output
                    snapshot=guardian.snapshot(fresh=True)
                    if snapshot.get('remaining',{}).get('minute_tokens',-1)<estimate:raise QuotaDenied('quota_minute_tokens')
                    if groq_extension and (snapshot.get('remaining',{}).get('daily_tokens',0)<2*estimate or snapshot.get('remaining',{}).get('daily_requests',0)<10):
                        raise QuotaDenied('task_budget_extension_capacity_insufficient')
                    if groq_extension:state['task_budget_extension']={'provider':'groq','initial_limit':self.options['max_task_cloud_calls'],'task_limit':task_call_limit,'reason':options['native_groq_budget_reason']}
                    sent=True;message=adapter.complete(outbound,output_tokens=output,cancelled=cancelled,json_mode=True,
                        request_id=identifier,coding_context=context,task_id=task_id,task_limit=task_call_limit)
                else:
                    from .coding_cloud_context import function_generation_envelope
                    wire_schema=function_generation_envelope(schema) if (options.get('native_exact_edit_spans') or {}).get('function_contract') else schema
                    sent=True;message=adapter.complete(outbound,schema=wire_schema,context=context,cancelled=cancelled,task_id=task_id,
                        task_limit=task_call_limit,request_id=identifier)
                from .structured_output import decode
                value=decode(message['content'],completed=True,reason='stop',schema=schema,directory=directory,stage='tool',
                    metadata={'provider':provider,'model':adapter.options['model'],'request_id':identifier})
                with guardian.connect() as db:
                    row=db.execute('SELECT usage FROM calls WHERE id=?',(identifier,)).fetchone()
                    if row:usage=json.loads(row['usage'])
                entry={'provider':provider,'model':adapter.options['model'],'request_id':identifier,'reason':'direct_assignment' if preference!='auto' else 'complex_task' if complex_task else 'verified_reasoning_escalation',
                       'latency_ms':round((time.monotonic()-started)*1000,3),'sent':True,'valid_proposal':True,'usage':usage,'application_verified':False,
                       'source_sha256':source_sha,'task_call_limit':task_call_limit,'tool':value.get('tool','structured_plan')}
                state['cloud_calls']+=1;state['attempts'].append(entry);atomic(state_path,json.dumps(state))
                self.gateway.performance.coding_result(identifier,provider,adapter.options['model'],stage,entry['latency_ms'],True,tokens=usage.get('total_tokens'))
                return value
            except (CloudFailure,QuotaDenied,ValueError,OSError) as error:
                # Provider inferences are read-only proposals. No local tool
                # action has executed, so bounded cross-provider inference is safe.
                try:
                    with guardian.connect() as db:row=db.execute('SELECT usage FROM calls WHERE id=?',(identifier,)).fetchone()
                except Exception:row=None
                dispatched=row is not None
                reason=str(error) if str(error).replace('_','').isalnum() and len(str(error))<=100 else 'invalid_structured_output'
                if dispatched:state['cloud_calls']+=1
                state['attempts'].append({'provider':provider,'model':adapter.options['model'],'request_id':identifier,'sent':dispatched,'reason':reason,
                    'valid_proposal':False,'source_sha256':source_sha,'task_call_limit':task_call_limit,'usage':json.loads(row['usage']) if row else {},
                    'latency_ms':round((time.monotonic()-started)*1000,3),'application_verified':False})
                if source_sha and isinstance(getattr(error,'previous_proposal',None),dict):
                    rejected=error.previous_proposal.get('tool')
                    detail=str(error).split(' Evidence: ')[0][:500]
                    if SECRET.search(detail):detail='Validation failed; private details withheld.'
                    state['last_validation_feedback']={'source_sha256':source_sha,
                        'schema_sha256':hashlib.sha256(json.dumps(schema,sort_keys=True).encode()).hexdigest(),
                        'expected_tool':options.get('native_required_tool'),'rejected_tool':rejected if rejected in {'Read','read_batch','Write','Edit','edit_batch','run_checks','finish'} else 'other',
                        'validation_error':detail,'action_executed':False}
                if getattr(error,'details',None):state['attempts'][-1]['context_budget']=error.details
                if getattr(error,'provider_diagnostic',None):
                    state['attempts'][-1]['provider_error']=error.provider_diagnostic
                if getattr(error,'provider_message',None):
                    from .structured_output import preserve
                    evidence=preserve(directory,'provider-error',error.provider_message,
                        {'provider':provider,'model':adapter.options['model'],'request_id':identifier,'completed':False,
                         'executable':False,'origin':'private provider error message, key-redacted','provider_error':error.provider_diagnostic})
                    state['attempts'][-1]['private_provider_error_evidence']=str(Path(evidence).relative_to(directory))
                if getattr(error,'rejected_generation',None):
                    from .structured_output import preserve
                    evidence=preserve(directory,'provider-rejected',error.rejected_generation,
                        {'provider':provider,'model':adapter.options['model'],'request_id':identifier,
                         'completed':False,'provider_error':error.provider_diagnostic})
                    state['attempts'][-1]['provider_rejection_evidence']=str(Path(evidence).relative_to(directory))
                atomic(state_path,json.dumps(state))
                metered=json.loads(row['usage']).get('total_tokens') if row else None
                self.gateway.performance.coding_result(identifier,provider,adapter.options['model'],stage,(time.monotonic()-started)*1000,False,reason=reason,tokens=metered)
                if cancelled() or time.monotonic()>=deadline:raise CloudFailure('cancelled')
        atomic(state_path,json.dumps(state))
        return None

    def status(self):
        options=self.gemini_options;margin=1-options['safety_margin']
        return {'gemini':{'state':self.gemini_guardian.snapshot(fresh=True) if self.gemini_guardian else 'UNAVAILABLE',
                          'reason':self.gemini_reason,'project':self.gemini_options['api_project_id'],
                          'model':self.gemini_options['model'],'provider_limits':{'rpm':options['max_minute_requests'],'input_tpm':options['max_minute_input_tokens'],'rpd':options['max_daily_requests']},
                          'jarvis_limits':{'rpm':int(options['max_minute_requests']*margin),'input_tpm':int(options['max_minute_input_tokens']*margin),
                                           'rpd':int(options['max_daily_requests']*margin),'concurrent':options['max_concurrent_calls'],
                                           'per_task':min(self.options['gemini_max_task_calls'],options['max_task_calls'])},
                          'daily_token_limit':None},'coding_enabled':self.options['enabled'],'dry_run_verified':self.options['dry_run_verified']}
