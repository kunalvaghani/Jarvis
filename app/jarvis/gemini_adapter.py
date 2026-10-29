"""Free-only Gemini Interactions transport; proposals never execute here."""
import json
import threading
import time
import uuid
from email.utils import parsedate_to_datetime
import requests
from .coding_cloud_policy import approved_payload, gemini_eligible
from .groq_adapter import CloudFailure,provider_failure

ENDPOINT='https://generativelanguage.googleapis.com/v1beta/interactions'


class GeminiAdapter:
    def __init__(self,key,options,guardian,transport=None):
        self.key,self.options,self.guardian=key,options,guardian
        self.client=transport or requests.Session();self.client.trust_env=False
        self.closed=threading.Event()

    def close(self):
        self.closed.set();self.client.close()

    def refresh_clock(self,cancelled):
        """Read-only model metadata, not an inference or quota entitlement probe."""
        response=None
        try:
            if cancelled() or self.closed.is_set():raise CloudFailure('cancelled')
            url='https://generativelanguage.googleapis.com/v1beta/models/'+self.options['model']
            response=self.client.get(url,headers={'x-goog-api-key':self.key},timeout=(3,5),stream=True,allow_redirects=False)
            if response.status_code!=200:raise CloudFailure('model_metadata_unavailable')
            raw=bytearray()
            for chunk in response.iter_content(4096):
                raw.extend(chunk)
                if len(raw)>32000 or cancelled():raise CloudFailure('metadata_budget_or_cancelled')
            if json.loads(raw).get('name')!='models/'+self.options['model']:raise CloudFailure('model_metadata_mismatch')
            headers={key.lower():value for key,value in response.headers.items()}
            self.guardian.confirm_clock(parsedate_to_datetime(headers['date']).timestamp())
        except CloudFailure:raise
        except Exception:raise CloudFailure('model_metadata_unavailable') from None
        finally:
            if response is not None:response.close()

    def complete(self,messages,*,schema=None,tools=None,context=None,output_tokens=None,cancelled=lambda:False,
                 task_id=None,task_limit=None,request_id=None,thinking=None):
        reason=gemini_eligible(self.options,self.key)
        if reason:raise CloudFailure(reason)
        if self.closed.is_set() or cancelled():raise CloudFailure('cancelled')
        snapshot=self.guardian.snapshot(fresh=True)
        if snapshot.get('reason')=='clock_change_requires_metadata':self.refresh_clock(cancelled)
        if schema is not None and tools:raise CloudFailure('separate_structured_and_function_modes')
        messages=approved_payload(messages,context)
        output_tokens=output_tokens or self.options['max_output_tokens']
        if type(output_tokens) is not int or not 1<=output_tokens<=self.options['max_output_tokens']:raise CloudFailure('output_budget_invalid')
        thinking=thinking or self.options['thinking']
        if thinking not in ('low','medium','high'):raise CloudFailure('unsupported_reasoning')
        payload={'model':self.options['model'],'store':False,'stream':False,
                 'input':[{'role':'model' if row['role']=='assistant' else 'user','content':[{'type':'text','text':row['content']}]} for row in messages if row['role']!='system'],
                 'system_instruction':'\n'.join(row['content'] for row in messages if row['role']=='system'),
                 'generation_config':{'max_output_tokens':output_tokens,'thinking_level':thinking}}
        if schema is not None:
            from .structured_output import generation_schema
            payload['response_format']={'type':'text','mime_type':'application/json','schema':generation_schema(schema)}
        if tools:payload['tools']=[{'type':'function',**tool['function']} for tool in tools]
        endpoint=ENDPOINT
        content_api=self.options.get('api_protocol','interactions')=='generate_content'
        if content_api:
            if tools:raise CloudFailure('generate_content_function_mode_not_enabled')
            config={'maxOutputTokens':output_tokens,'thinkingConfig':{'thinkingLevel':thinking.upper()}}
            if schema is not None:
                from .structured_output import generation_schema
                config.update(responseMimeType='application/json',responseJsonSchema=generation_schema(schema))
            payload={'contents':[{'role':'model' if row['role']=='assistant' else 'user','parts':[{'text':row['content']}]} for row in messages if row['role']!='system'],
                     'systemInstruction':{'parts':[{'text':'\n'.join(row['content'] for row in messages if row['role']=='system')}]},
                     'generationConfig':config}
            endpoint='https://generativelanguage.googleapis.com/v1beta/models/'+self.options['model']+':generateContent'
        estimate=len(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())+256
        request_id=request_id or uuid.uuid4().hex
        identifier=self.guardian.reserve(self.options['model'],estimate+output_tokens,request_id,
            input_tokens=estimate,output_tokens=output_tokens,task_id=task_id or request_id,task_limit=task_limit or self.options['max_task_calls'])
        response=None;usage=None;response_id='';succeeded=False;done=threading.Event();started=time.monotonic()
        def stop():return self.closed.is_set() or cancelled() or time.monotonic()-started>=self.options['timeout_seconds']
        def watch():
            while not done.wait(.02):
                if stop():
                    if response is not None:response.close()
                    return
        thread=threading.Thread(target=watch,name='gemini-deadline',daemon=True);thread.start()
        try:
            if stop():raise CloudFailure('cancelled_before_dispatch')
            response=self.client.post(endpoint,json=payload,headers={'x-goog-api-key':self.key},stream=True,
                timeout=(3,self.options['timeout_seconds']),allow_redirects=False)
            if response.status_code!=200:
                if response.status_code==429:
                    try:delay=float(response.headers.get('Retry-After',response.headers.get('retry-after',60)))
                    except (ValueError,TypeError):delay=60
                    error_bytes=bytearray()
                    try:
                        for chunk in response.iter_content(4096):
                            error_bytes.extend(chunk)
                            if len(error_bytes)>16000:break
                        details=json.loads(error_bytes).get('error',{}).get('details',[])
                        from .cloud_quota import duration
                        for detail in details:
                            if str(detail.get('@type','')).endswith('RetryInfo'):delay=max(delay,duration(detail.get('retryDelay')) or 0)
                            for violation in detail.get('violations',[]):
                                label=str(violation.get('quotaId','')).lower()
                                if 'perday' in label:
                                    reset=self.guardian.snapshot(fresh=True).get('daily_reset_at',self.guardian.clock()+86400)
                                    self.guardian.feedback('daily_requests',remaining=0,reset_at=reset,request_id=identifier)
                                    delay=max(delay,reset-self.guardian.clock())
                                elif 'perminute' in label:
                                    dimension='minute_input_tokens' if 'token' in label else 'minute_requests'
                                    self.guardian.feedback(dimension,remaining=0,reset_at=self.guardian.clock()+max(60,delay),request_id=identifier)
                    except (ValueError,TypeError,KeyError):pass
                    self.guardian.block(delay)
                else:self.guardian.block(60 if response.status_code in (401,403,404) else 30)
                if response.status_code!=429:raise provider_failure(response,redactions=(self.key,))
                raise CloudFailure('provider_http_'+str(response.status_code))
            raw=bytearray()
            for chunk in response.iter_content(4096):
                if stop():raise CloudFailure('cancelled_or_timeout')
                raw.extend(chunk)
                if len(raw)>150000:raise CloudFailure('response_oversized')
            if stop():raise CloudFailure('cancelled_or_timeout')
            data=json.loads(raw)
            if content_api:
                metering=data.get('usageMetadata',{});reported={}
                if 'promptTokenCount' in metering:reported['total_input_tokens']=metering['promptTokenCount']
                if 'totalTokenCount' in metering:reported['total_tokens']=metering['totalTokenCount']
                if type(metering.get('totalTokenCount')) is int and type(metering.get('promptTokenCount')) is int:
                    if metering['totalTokenCount']<metering['promptTokenCount']:raise CloudFailure('provider_usage_invalid')
                    reported['total_output_tokens']=metering['totalTokenCount']-metering['promptTokenCount']
                elif type(metering.get('candidatesTokenCount')) is int:
                    reported['total_output_tokens']=metering['candidatesTokenCount']+metering.get('thoughtsTokenCount',0)
                candidates=data.get('candidates',[]);candidate=candidates[0] if len(candidates)==1 else {}
                parts=candidate.get('content',{}).get('parts',[])
                steps=[{'type':'model_output','content':[{'type':'text','text':part['text']} for part in parts if isinstance(part.get('text'),str) and not part.get('thought')]}]
                if any('functionCall' in part for part in parts):steps.append({'type':'function_call'})
                data={'id':data.get('responseId',''),'usage':reported,'status':'completed' if candidate.get('finishReason')=='STOP' else 'incomplete','steps':steps}
            response_id=data.get('id','');reported=data.get('usage',{})
            usage={target:reported[key] for target,key in [('prompt_tokens','total_input_tokens'),('completion_tokens','total_output_tokens'),('total_tokens','total_tokens')] if key in reported}
            if data.get('status') not in (('completed','requires_action') if tools else ('completed',)):raise CloudFailure('incomplete_output')
            steps=data.get('steps',[]);calls=[step for step in steps if step.get('type')=='function_call']
            if calls:
                if not tools or len(calls)!=1:raise CloudFailure('invalid_tool_proposal')
                call=calls[0];offered=next((tool['function'] for tool in tools if tool['function']['name']==call.get('name')),None)
                if not offered:raise CloudFailure('invalid_tool_proposal')
                from .structured_output import validate_contract
                validate_contract(offered['parameters'],call.get('arguments'))
                result={'content':None,'tool_calls':[{'id':call.get('id',''),'type':'function','function':{
                    'name':call['name'],'arguments':json.dumps(call['arguments'])}}]}
            else:
                text=''.join(part.get('text','') for step in steps if step.get('type')=='model_output'
                             for part in step.get('content',[]) if part.get('type')=='text')
                if not text.strip():raise CloudFailure('empty_answer')
                if schema is not None:
                    from .structured_output import validate_contract
                    validate_contract(schema,json.loads(text))
                result={'content':text}
            succeeded=True
            return result
        except CloudFailure:raise
        except Exception as error:
            self.guardian.block(30)
            timed_out=isinstance(error,requests.Timeout) or time.monotonic()-started>=self.options['timeout_seconds']
            failure=CloudFailure('gemini_timeout' if timed_out else 'gemini_transport_or_protocol_failure')
            if timed_out:failure.provider_diagnostic={'category':'timeout','phase':'headers' if response is None else 'response_body'}
            raise failure from None
        finally:
            done.set()
            if response is not None:response.close()
            try:self.guardian.finish(identifier,usage,status='complete' if succeeded else 'failed',response_id=response_id)
            except Exception:raise CloudFailure('quota_reconciliation_uncertain') from None
