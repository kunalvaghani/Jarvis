"""Optional, page-bound experimental WebMCP adapter; disabled by default.

Uses an already owned Playwright page. No browser/model/server is started here.
Site annotations never authorize actions. Host policy pins origin, name, input
and output schemas; every invocation needs authorization and verification.
There is deliberately no automatic retry or fallback after invocation starts.
"""
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from .mcp_contract import ANNOTATIONS, SUPPORTED, ContractError, validate_schema_value


class UncertainExecution(RuntimeError):
    """Invocation may have had effects: observe state before further actions."""


def bounded_json(value, limit=16000):
    try:
        raw=json.dumps(value,allow_nan=False,ensure_ascii=False,separators=(',',':'))
    except (ValueError,TypeError,RecursionError) as error:
        raise ContractError('WebMCP requires bounded JSON data.') from error
    if len(raw.encode('utf-8'))>limit:raise ContractError('WebMCP JSON exceeds its byte budget.')
    return json.loads(raw)


def checked_schema(schema):
    from jsonschema import Draft202012Validator
    schema=bounded_json(schema,8000)
    Draft202012Validator.check_schema(schema)
    def visit(node,depth=0):
        if depth>8 or not isinstance(node,dict):raise ContractError('Unsupported WebMCP schema depth/type.')
        if set(node)-SUPPORTED-ANNOTATIONS:raise ContractError('Unsupported WebMCP schema keyword.')
        for child in node.get('properties',{}).values():visit(child,depth+1)
        if 'items' in node:visit(node['items'],depth+1)
        if isinstance(node.get('additionalProperties'),dict):visit(node['additionalProperties'],depth+1)
    visit(schema)
    return schema


def origin(url):
    parsed=urlsplit(url)
    if parsed.username or parsed.password or parsed.scheme not in {'https','http'}:raise ContractError('WebMCP needs an HTTP origin without credentials.')
    if parsed.scheme=='http' and parsed.hostname not in {'127.0.0.1','localhost','::1'}:raise ContractError('WebMCP requires a trustworthy origin.')
    port=parsed.port
    host=parsed.hostname or ''
    if ':' in host:host='['+host+']'
    return parsed.scheme+'://'+host+(':'+str(port) if port and port!={'http':80,'https':443}[parsed.scheme] else '')


DISCOVER = """async () => {
 const doc=document, url=location.href, api=doc.modelContext;
 const supported=isSecureContext && !!api && ['getTools','executeTool'].every(k=>typeof api[k]==='function');
 if(!supported)return {supported:false};
 const state={supported:true,doc,url,api,epoch:0,tools:[],pending:null};
 state.changed=()=>state.epoch++;
 api.addEventListener('toolchange',state.changed);
 try {
  let timer;
  try {state.tools=await Promise.race([api.getTools(),new Promise((_,reject)=>{
   timer=setTimeout(()=>reject(Error('Discovery deadline')),2000);})]);}
  finally {clearTimeout(timer);}
  if(!Array.isArray(state.tools)||state.tools.length>32)throw Error('Tool catalogue budget');
  state.version=state.epoch;
  state.rows=state.tools.map((t,index)=>({index,name:t.name,description:t.description,
   inputSchema:t.inputSchema,origin:t.origin,sameWindow:t.window===window}));
  const raw=JSON.stringify(state.rows);
  if(new TextEncoder().encode(raw).length>16000)throw Error('Tool metadata budget');
  return state;
 } catch(e) {api.removeEventListener('toolchange',state.changed);throw e;}
}"""

START = """(s,request) => {
 if(document!==s.doc||location.href!==s.url||s.epoch!==s.version||s.pending)throw Error('Stale WebMCP registration');
 const tool=s.tools[request.index];
 if(!tool||tool.name!==request.name||tool.window!==window||tool.origin!==location.origin)throw Error('WebMCP tool/frame/origin changed');
 const controller=new AbortController();
 s.pending={status:'pending',controller};
 Promise.resolve().then(()=>s.api.executeTool(tool,request.arguments,{signal:controller.signal})).then(result=>{
  if(result===null)throw Error('Navigation or null result requires observation');
  const raw=JSON.stringify(result);
  if(typeof raw!=='string'||new TextEncoder().encode(raw).length>16000)throw Error('Result budget/type');
  s.pending.result=JSON.parse(raw);s.pending.status='done';
 }).catch(()=>{s.pending.status='error';});
 return true;
}"""

POLL = """s => {
 if(document!==s.doc||location.href!==s.url||s.epoch!==s.version)return {status:'stale'};
 return {status:s.pending?.status,result:s.pending?.status==='done'?s.pending.result:undefined};
}"""


class PageTools:
    def __init__(self,page,policies,*,enabled=False,cancelled=lambda:False,journal=None,result_encoding='json-value'):
        self.page=page
        self.enabled=enabled is True
        self.cancelled=cancelled
        self.journal=journal
        self.retired=False
        if result_encoding not in {'json-value','json-text'}:raise ContractError('Unsupported WebMCP result encoding.')
        self.result_encoding=result_encoding
        self.policies={}
        self.handle=None
        self.rows=[]
        self.audits=[]
        self.probed=False
        self.bound_url=page.url
        for policy in policies:
            policy=bounded_json(policy)
            if set(policy)!={'origin','name','operation','inputSchema','outputSchema'}:raise ContractError('WebMCP policy must pin the complete host contract.')
            if origin(policy['origin'])!=policy['origin'] or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',policy['name']):raise ContractError('Invalid host WebMCP binding.')
            if not isinstance(policy['operation'],str) or not 1<=len(policy['operation'])<=80:raise ContractError('Invalid trusted operation.')
            policy['inputSchema']=checked_schema(policy['inputSchema'])
            policy['outputSchema']=checked_schema(policy['outputSchema'])
            key=(policy['origin'],policy['name'])
            if key in self.policies:raise ContractError('Duplicate WebMCP policy.')
            self.policies[key]=policy

    def discover(self):
        if not self.enabled or self.cancelled() or self.probed:return [dict(row) for row in self.rows]
        self.probed=True  # Negative capability results are cached for this lifecycle.
        if self.page.url!=self.bound_url:raise ContractError('Create a fresh binding after navigation.')
        self.handle=self.page.evaluate_handle(DISCOVER)
        data=self.handle.evaluate('(s)=>({supported:s.supported,rows:s.rows||[]})')
        if not data['supported']:return []
        for row in bounded_json(data['rows']):
            policy=self.policies.get((row.get('origin'),row.get('name')))
            if not policy or row.get('sameWindow') is not True:continue
            if row['origin']!=origin(self.page.url):continue
            if checked_schema(row.get('inputSchema'))!=policy['inputSchema']:continue
            self.rows.append({'index':row['index'],'name':row['name'],'origin':row['origin'],
                              'operation':policy['operation'],'untrusted':True})
        return [dict(row) for row in self.rows]

    def select(self,operation):
        if self.retired:return None
        matches=[row for row in self.discover() if row['operation']==operation]
        if matches:
            try:fresh=self.handle.evaluate('(s)=>document===s.doc&&location.href===s.url&&s.epoch===s.version')
            except Exception:fresh=False
            if not fresh:
                self.rows=[]
                self.retired=True
                return None
        return dict(matches[0]) if len(matches)==1 else None

    def execute(self,operation,arguments,*,authorize,verify,seconds=5):
        if type(seconds) not in {int,float} or not .1<=seconds<=10:raise ContractError('WebMCP timeout must be0.1..10 seconds.')
        row=self.select(operation)
        if not row:raise ContractError('No eligible WebMCP tool; existing browser fallback is available.')
        if not callable(self.journal):raise ContractError('WebMCP requires a host execution journal.')
        policy=self.policies[(row['origin'],row['name'])]
        arguments=bounded_json(arguments,8000)
        validate_schema_value(policy['inputSchema'],arguments)
        if self.cancelled():raise ContractError('Cancelled before invocation.')
        if authorize(dict(row),bounded_json(arguments)) is not True:raise PermissionError('WebMCP invocation was not authorized.')
        if self.cancelled():raise ContractError('Cancelled before invocation.')
        audit={'name':row['name'],'origin':row['origin'],'state':'intent',
               'arguments_sha256':hashlib.sha256(json.dumps(arguments,sort_keys=True).encode()).hexdigest()}
        self.audits.append(audit)
        self.journal(dict(audit))  # Must succeed durably before any dispatch.
        started=time.monotonic()
        try:
            # Once attempted, any failure is uncertain. Never replay or fall back.
            self.handle.evaluate(START,{'index':row['index'],'name':row['name'],'arguments':arguments})
            while True:
                if self.cancelled() or time.monotonic()-started>=seconds:raise TimeoutError('WebMCP cancelled or deadline reached.')
                result=self.handle.evaluate(POLL)
                if result['status']=='done':break
                if result['status']!='pending':raise RuntimeError('WebMCP failed or lifecycle changed.')
                time.sleep(.025)
            value=bounded_json(result['result'])
            if self.result_encoding=='json-text':
                if not isinstance(value,str):raise ContractError('Expected explicitly pinned JSON-text transport.')
                value=bounded_json(json.loads(value))
            validate_schema_value(policy['outputSchema'],value,'result')
            if verify(bounded_json(value)) is not True:raise ContractError('Independent result verification failed.')
            if not self.handle.evaluate('(s)=>document===s.doc&&location.href===s.url&&s.epoch===s.version'):
                raise ContractError('WebMCP lifecycle changed during result verification.')
            audit['state']='verified'
            self.handle.evaluate('(s)=>{s.pending=null;}')
            return {'result':value,'untrusted':True,'verified':True}
        except Exception as error:
            audit['state']='uncertain'
            self.retired=True
            try:self.handle.evaluate('(s)=>s.pending?.controller.abort()')
            except Exception:pass
            raise UncertainExecution('WebMCP attempt requires fresh observation; no retry or automatic fallback.') from error
        finally:
            audit['seconds']=round(time.monotonic()-started,4)
            self.journal(dict(audit))

    def close(self):
        if self.handle:
            try:self.handle.evaluate('(s)=>{s.pending?.controller.abort();s.api?.removeEventListener("toolchange",s.changed);}')
            except Exception:pass
            try:self.handle.dispose()
            except Exception:pass
        self.handle=None
        self.rows=[]
        self.retired=True
