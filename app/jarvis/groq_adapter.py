"""Bounded Groq OpenAI-compatible transport. Never executes proposed tools."""
from datetime import timezone
from email.utils import parsedate_to_datetime
import json
import threading
import time
import requests
import base64
import hashlib
import io

from .cloud_policy import screen_payload

ENDPOINT='https://api.groq.com/openai/v1'


class CloudFailure(ValueError):
    def __init__(self, reason, partial=False):
        super().__init__(reason); self.partial=partial


def provider_failure(response,redactions=()):
    """Retain categorical error and bounded rejected model text, never free-form error messages."""
    failure=CloudFailure('provider_http_'+str(response.status_code))
    try:
        raw=b''
        for chunk in response.iter_content(4096):
            raw+=chunk
            if len(raw)>64000:return failure
        data=json.loads(raw);error=data.get('error',{})
        codes={'json_validate_failed','tool_use_failed','context_length_exceeded','invalid_api_key',
               'rate_limit_exceeded','model_not_found','unsupported_parameter','invalid_request_error','invalid_request'}
        types={'invalid_request_error','authentication_error','rate_limit_error','server_error','tokens','requests'}
        failure.provider_diagnostic={'http_status':response.status_code,
            'code':error.get('code') if error.get('code') in codes else 'unclassified',
            'type':error.get('type') if error.get('type') in types else 'unclassified'}
        status=error.get('status')
        if status in {'INVALID_ARGUMENT','PERMISSION_DENIED','NOT_FOUND','RESOURCE_EXHAUSTED','UNAUTHENTICATED','INTERNAL','UNAVAILABLE'}:
            failure.provider_diagnostic['status']=status
        private_message=error.get('message','')
        if isinstance(private_message,str) and len(private_message.encode())<=3000:
            for secret in redactions:
                if isinstance(secret,str) and secret:private_message=private_message.replace(secret,'[REDACTED]')
            from .coding_cloud_policy import SECRET
            if private_message and not SECRET.search(private_message):failure.provider_message=private_message
        message=error.get('message','')
        message=message.lower() if isinstance(message,str) else ''
        if ('schema' in message or 'constraint' in message) and any(word in message for word in ('complex','states','branch','nested')):
            failure.provider_diagnostic['category']='schema_too_complex'
        elif ('pattern' in message or 'regex' in message) and any(word in message for word in ('invalid','unsupported')):
            failure.provider_diagnostic['category']='unsupported_schema_pattern'
        elif 'unknown name' in message or 'unknown field' in message:
            failure.provider_diagnostic['category']='unsupported_request_field'
        elif 'json' in message and 'fail' in message:
            failure.provider_diagnostic['category']='invalid_generated_json'
        generation=error.get('failed_generation')
        if isinstance(generation,str):
            from .coding_cloud_policy import SECRET
            withheld=len(generation.encode())>16000 or bool(SECRET.search(generation)) or any(isinstance(secret,str) and secret and secret in generation for secret in redactions)
            failure.provider_diagnostic['rejected_generation_withheld']=withheld
            if not withheld:failure.rejected_generation=generation
    except (ValueError,TypeError,AttributeError):pass
    return failure


class GroqAdapter:
    def __init__(self, key, options, guardian, transport=None, endpoint=ENDPOINT, testing=False):
        if endpoint!=ENDPOINT and not (testing and endpoint.startswith('http://127.0.0.1:')):
            raise ValueError('Groq transport requires its fixed HTTPS endpoint.')
        self.key,self.options,self.guardian=key,options,guardian
        self.endpoint=endpoint
        self.client=transport or requests.Session(); self.client.trust_env=False
        self.available_until=0.; self.next_refresh=0.; self.thread=None; self.closed=threading.Event(); self.lock=threading.Lock()

    def close(self):
        self.closed.set(); self.client.close()

    def refresh_async(self):
        with self.lock:
            if self.closed.is_set() or time.monotonic()<max(self.next_refresh,self.available_until) or (self.thread and self.thread.is_alive()): return
            self.thread=threading.Thread(target=self.refresh,name='groq-metadata',daemon=True)
            self.thread.start()

    def refresh(self):
        if self.closed.is_set(): return
        try:
            started=time.monotonic()
            with self.client.get(self.endpoint+'/models',headers={'Authorization':'Bearer '+self.key},timeout=(3,5),stream=True,allow_redirects=False) as response:
                if response.status_code!=200: raise CloudFailure('metadata_unavailable')
                raw=bytearray()
                for chunk in response.iter_content(4096):
                    raw.extend(chunk)
                    if len(raw)>100000 or self.closed.is_set() or time.monotonic()-started>8:
                        raise CloudFailure('metadata_budget_exceeded')
                models=json.loads(raw).get('data',[])
                if not any(r.get('id')==self.options['model'] and r.get('active',True) for r in models if isinstance(r,dict)):
                    raise CloudFailure('model_unavailable')
                server=parsedate_to_datetime(response.headers['Date']).astimezone(timezone.utc).timestamp()
                self.guardian.confirm_clock(server)
                if not self.closed.is_set(): self.available_until=time.monotonic()+self.options['metadata_ttl_seconds']
        except Exception:
            self.available_until=0
            self.next_refresh=time.monotonic()+30

    def ready(self, wait_seconds=0):
        if time.monotonic()>=self.available_until:
            self.refresh_async()
            thread = self.thread
            if wait_seconds and thread and thread is not threading.current_thread():
                thread.join(timeout=min(8, max(0, wait_seconds)))
            if time.monotonic()>=self.available_until:
                return False
        return not self.closed.is_set()

    def complete(self,messages,output_tokens=512,on_chunk=None,cancelled=lambda:False,tools=None,json_mode=False,reasoning='none',request_id=None,approved_image_hashes=(),coding_context=None,task_id=None,task_limit=None):
        if (not self.options['enabled'] or self.options['routing']=='local' or not self.options['free_only'] or
                self.options['account_plan']!='free' or not self.options['free_tier_confirmed'] or not self.options['dedicated_quota_confirmed']):
            raise CloudFailure('free_dispatch_policy_not_confirmed')
        if self.closed.is_set() or cancelled(): raise CloudFailure('cancelled')
        if not self.ready(): raise CloudFailure('metadata_not_ready')
        if reasoning not in {'none','low','medium','high'}: raise CloudFailure('unsupported_reasoning')
        if type(output_tokens) is not int or not 1<=output_tokens<=self.options['max_output_tokens']:
            raise CloudFailure('output_budget_invalid')
        if coding_context is not None:
            from .coding_cloud_policy import approved_payload,token_estimate
            messages=approved_payload(messages,coding_context)
            amount=token_estimate({'messages':messages,'tools':tools or []})+output_tokens
        else:amount=screen_payload({'messages':messages,'tools':tools or []})+output_tokens
        images=0
        for message in messages:
            if not isinstance(message,dict) or message.get('role') not in {'system','user','assistant','tool'}:
                raise CloudFailure('invalid_message_role')
            if isinstance(message.get('content'),list):
                for part in message['content']:
                    if part.get('type')!='image_url': continue
                    images+=1;url=part.get('image_url',{}).get('url','')
                    if not url.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):
                        raise CloudFailure('Only exact approved embedded images are supported; no provider URL fetch.')
                    try: raw=base64.b64decode(url.split(',',1)[1],validate=True)
                    except ValueError: raise CloudFailure('invalid_image') from None
                    if len(raw)>4096 or hashlib.sha256(raw).hexdigest() not in approved_image_hashes:
                        raise CloudFailure('image_upload_not_scoped_or_oversized')
                    from PIL import Image
                    with Image.open(io.BytesIO(raw)) as picture:
                        if picture.width*picture.height>262144: raise CloudFailure('image_resolution_budget')
                    amount+=4096  # conservative extra allowance for small-image visual tokens
        if images>1: raise CloudFailure('free_quota_allows_only_one_small_approved_image')
        if tools and on_chunk: raise CloudFailure('streamed_tools_not_supported')
        if json_mode and tools:raise CloudFailure('separate_structured_and_function_modes')
        identifier=self.guardian.reserve(self.options['model'],amount,request_id,input_tokens=amount-output_tokens,output_tokens=output_tokens,
            **({'task_id':task_id,'task_limit':task_limit} if task_id is not None else {}))
        payload={'model':self.options['model'],'messages':messages,'max_completion_tokens':output_tokens,
            'reasoning_effort':reasoning,'reasoning_format':'hidden','stream':on_chunk is not None}
        if json_mode: payload['response_format']={'type':'json_object'}
        if tools: payload.update(tools=tools,parallel_tool_calls=False)
        usage=None; headers={}; response_id=''; partial=False; response=None; stop=threading.Event(); succeeded=False
        started=time.monotonic()
        # A deadline/cancellation closes the socket even if no stream bytes arrive.
        def deadline():
            while not stop.wait(.02):
                if cancelled() or time.monotonic()-started>self.options['timeout_seconds']:
                    if response is not None: response.close()
                    return
        watchdog=threading.Thread(target=deadline,name='groq-deadline',daemon=True); watchdog.start()
        try:
            if cancelled(): raise CloudFailure('cancelled_before_dispatch')
            response=self.client.post(self.endpoint+'/chat/completions',json=payload,
                headers={'Authorization':'Bearer '+self.key},stream=True,
                timeout=(3,self.options['timeout_seconds']),allow_redirects=False)
            headers={str(key).lower():str(value) for key,value in response.headers.items()}
            if response.status_code!=200:
                if response.status_code==429:
                    try: delay=float(headers.get('retry-after','60'))
                    except ValueError: delay=60
                    self.guardian.block(delay)
                elif response.status_code in {401,403,404}:
                    self.available_until=0;self.next_refresh=time.monotonic()+60
                else: self.guardian.block(30)
                raise provider_failure(response,redactions=(self.key,))
            if not payload['stream']:
                raw=b''
                for chunk in response.iter_content(4096):
                    if cancelled() or time.monotonic()-started>self.options['timeout_seconds']: raise CloudFailure('cancelled_or_timeout')
                    raw+=chunk
                    if len(raw)>100000: raise CloudFailure('response_oversized')
                data=json.loads(raw); usage=data.get('usage'); response_id=data.get('id','')
                choice=data['choices'][0]
                if choice.get('finish_reason') == 'length': raise CloudFailure('output_token_limit')
                if choice.get('finish_reason') not in {'stop','tool_calls'}: raise CloudFailure('incomplete_output')
                message=choice['message']
                if tools and message.get('tool_calls'):
                    allowed={t['function']['name'] for t in tools}
                    calls=message['tool_calls']
                    if len(calls)!=1 or calls[0].get('function',{}).get('name') not in allowed:
                        raise CloudFailure('invalid_tool_proposal')
                    arguments=json.loads(calls[0]['function']['arguments'])
                    offered=next(t['function'] for t in tools if t['function']['name']==calls[0]['function']['name'])
                    from .repo_analysis import validate
                    validate(offered['parameters'],arguments)
                elif not isinstance(message.get('content'),str) or not message['content'].strip(): raise CloudFailure('empty_answer')
                if json_mode: json.loads(message['content'])
                succeeded=True
                return message
            if tools: raise CloudFailure('streamed_tools_not_supported')
            pieces=[]; size=0; done=False; finished=False
            def bounded_lines():
                pending=bytearray();wire=0
                for block in response.iter_content(chunk_size=512):
                    wire+=len(block)
                    if wire>1000000: raise CloudFailure('stream_wire_budget',partial)
                    if cancelled() or time.monotonic()-started>self.options['timeout_seconds']: raise CloudFailure('cancelled_or_timeout',partial)
                    pending.extend(block)
                    while b'\n' in pending:
                        boundary=pending.index(b'\n')
                        if boundary>100000: raise CloudFailure('stream_wire_budget',partial)
                        yield bytes(pending[:boundary]).rstrip(b'\r')
                        del pending[:boundary+1]
                    if len(pending)>100000: raise CloudFailure('stream_wire_budget',partial)
                if pending: yield bytes(pending)
            for line in bounded_lines():
                if cancelled() or time.monotonic()-started>self.options['timeout_seconds']: raise CloudFailure('cancelled_or_timeout',partial)
                if not line: continue
                if not line.startswith(b'data: '): continue
                if line==b'data: [DONE]': done=True; break
                data=json.loads(line[6:]); response_id=data.get('id',response_id)
                usage=data.get('usage') or data.get('x_groq',{}).get('usage') or usage
                for choice in data.get('choices',[]):
                    chunk=choice.get('delta',{}).get('content') or ''
                    if choice.get('finish_reason')=='stop': finished=True
                    elif choice.get('finish_reason')=='length': raise CloudFailure('output_token_limit',partial)
                    elif choice.get('finish_reason'): raise CloudFailure('incomplete_output',partial)
                    size+=len(chunk.encode())
                    if size>100000: raise CloudFailure('response_oversized',partial)
                    if chunk:
                        pieces.append(chunk); partial=True; on_chunk(chunk)
            if not done or not finished or not pieces: raise CloudFailure('incomplete_stream',partial)
            succeeded=True
            return {'content':''.join(pieces)}
        except CloudFailure:
            raise
        except Exception:
            self.guardian.block(30)
            cause = 'cloud_timeout' if time.monotonic()-started>=self.options['timeout_seconds'] else 'cloud_transport_or_protocol_failure'
            raise CloudFailure(cause,partial) from None
        finally:
            stop.set()
            if response is not None: response.close()
            try:
                self.guardian.finish(identifier,usage,headers,'complete' if succeeded else 'failed',response_id)
            except Exception:
                raise CloudFailure('Quota reconciliation failed; reservation retained, no automatic replay.',partial) from None
