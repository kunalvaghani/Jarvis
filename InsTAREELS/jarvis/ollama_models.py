"""Inspect local model visibility; rebuild owned aliases and import cached GGUF."""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

ENDPOINT = 'http://127.0.0.1:11434'
ALIAS_PARAMETERS = {'num_ctx':32768, 'num_gpu':9, 'temperature':0.2, 'num_predict':6000}
ALIASES = {'jarvis-codex-qwen3.5:9b':'qwen3.5:9b',
           'jarvis-claude-qwen3.5:9b':'qwen3.5:9b'}


class IncompleteCache(ValueError):
    """A resumable cache has metadata but is missing complete layer files."""


def local_endpoint(endpoint):
    parsed=urlsplit(endpoint)
    if parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.username or parsed.password or parsed.path not in {'','/'} or parsed.query or parsed.fragment:
        raise ValueError('Model restoration is restricted to a local Ollama server.')


def installed(client, endpoint=ENDPOINT):
    local_endpoint(endpoint)
    response=client.get(endpoint+'/api/tags',timeout=(3,10));response.raise_for_status()
    return {row['name'] for row in response.json().get('models',[])}


def model_plan(required):
    plan=[]
    for model in sorted(required):
        for name in ([ALIASES[model],model] if model in ALIASES else [model]):
            if name not in plan:plan.append(name)
    return plan


def create_alias(client, model, endpoint=ENDPOINT):
    local_endpoint(endpoint)
    if model not in ALIASES:raise ValueError('Unknown local Jarvis model alias.')
    parameters=dict(ALIAS_PARAMETERS)
    from .gpu_scheduler import configured
    policy=configured()
    if policy['enabled']:parameters['num_gpu']=policy['codex_layers']
    response=client.post(endpoint+'/api/create',json={'model':model,'from':ALIASES[model],
        'parameters':parameters,'stream':False},timeout=(3,60))
    response.raise_for_status()
    if response.json().get('status')!='success':raise ValueError('Local alias creation was not confirmed; inspect model visibility before continuing.')


def coding_model(client, model, endpoint=ENDPOINT):
    """Pre-task check: small alias repair only; never download weights here."""
    local_endpoint(endpoint)
    response=client.post(endpoint+'/api/show',json={'model':model},timeout=(3,10))
    if response.status_code==404:
        names=installed(client,endpoint)
        if model in names:
            raise ValueError('Ollama lists '+model+' but its /api/show endpoint returned 404. Check the active server API/version; no project files were changed.')
        if model in ALIASES and ALIASES[model] in names:
            create_alias(client,model,endpoint)
            response=client.post(endpoint+'/api/show',json={'model':model},timeout=(3,10))
        else:
            available=', '.join(sorted(names)) or '(none)'
            raise ValueError('Coding model '+model+' is not visible to Ollama at '+endpoint+
                '. This server lists: '+available+'. Windows and WSL can use different model stores. '
                'Run Setup Jarvis Brain.cmd to restore cached models, then retry. No project files were changed.')
    response.raise_for_status()
    data=response.json()
    if model in ALIASES and isinstance(data.get('parameters'),str):
        from .gpu_scheduler import configured
        policy=configured()
        wanted=policy['codex_layers'] if policy['enabled'] else ALIAS_PARAMETERS['num_gpu']
        current=re.search(r'^num_gpu\s+(-?\d+)\s*$',data['parameters'],re.M)
        if current is None or int(current[1])!=wanted:
            create_alias(client,model,endpoint)
            response=client.post(endpoint+'/api/show',json={'model':model},timeout=(3,10))
            response.raise_for_status();data=response.json()
    if 'tools' not in data.get('capabilities',[]):raise ValueError('Local Qwen model is missing tool support.')
    return data


def cache_roots(config):
    roots=list(config.get('brain',{}).get('ollama_cache_roots',[]))
    if os.environ.get('OLLAMA_MODELS'):roots.append(os.environ['OLLAMA_MODELS'])
    roots.append(str(Path.home()/'.ollama/models'))
    return list(dict.fromkeys(str(Path(root).expanduser()) for root in roots if isinstance(root,str) and root))


def cached_payload(root, model):
    """Validate the manifest and small metadata before sending any model bytes."""
    if not re.fullmatch(r'[\w.-]+:[\w.-]+',model):return None
    name,tag=model.split(':',1);root=Path(root).resolve()
    if name in {'.','..'} or tag in {'.','..'}:return None
    path=root/'manifests/registry.ollama.ai/library'/name/tag
    if not path.is_file():return None
    if path.stat().st_size>80000:raise ValueError('Cached model manifest is oversized.')
    manifest=json.loads(path.read_text(encoding='utf-8'))
    payload={'model':model,'files':{},'stream':False};weights=[];licenses=[]
    for layer in [manifest['config'],*manifest['layers']]:
        digest=layer['digest'];size=layer['size'];kind=layer['mediaType']
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',digest) or type(size) is not int or not 0<size<=100_000_000_000:
            raise ValueError('Invalid cached model layer descriptor.')
        blob=(root/'blobs'/digest.replace(':','-')).resolve()
        if not blob.is_relative_to(root/'blobs') or not blob.is_file() or blob.stat().st_size!=size:
            raise IncompleteCache('Cached model layer is missing or incomplete: '+model)
        if kind=='application/vnd.ollama.image.model':
            with blob.open('rb') as source:
                if source.read(4)!=b'GGUF':raise ValueError('Cached weights are not GGUF.')
            weights.append((blob,digest))
        else:
            if size>200000:raise ValueError('Unsupported cached model metadata size.')
            raw=blob.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=digest.split(':')[1]:raise ValueError('Cached model metadata checksum failed.')
            text=raw.decode('utf-8')
            if kind=='application/vnd.docker.container.image.v1+json':
                metadata=json.loads(text)
                for key in ('renderer','parser','requires'):
                    if metadata.get(key):payload[key]=metadata[key]
            elif kind=='application/vnd.ollama.image.params':payload['parameters']=json.loads(text)
            elif kind=='application/vnd.ollama.image.license':licenses.append(text)
            elif kind=='application/vnd.ollama.image.system':payload['system']=text
            elif kind=='application/vnd.ollama.image.template':payload['template']=text
            elif kind in {'application/vnd.ollama.manifest.list.v2+json',
                           'application/vnd.docker.distribution.manifest.v2+json'}:
                # Ollama's WriteLegacyAnchor appends manifest blobs only for
                # downgrade garbage-collection retention. They are not model
                # parameters or weights. Verify bounded metadata, never select
                # an alternate runner/projector or follow its references.
                metadata=json.loads(text)
                if (not isinstance(metadata,dict) or metadata.get('schemaVersion')!=2
                        or metadata.get('mediaType')!=kind):
                    raise ValueError('Invalid cached manifest anchor metadata.')
            else:raise ValueError('Unsupported cached model layer: '+kind)
    # Multi-part/projector models need their original filenames, which a registry
    # manifest does not retain. Do not guess them or silently omit a layer.
    if len(weights)!=1:raise ValueError('Cached multi-part model needs the normal Ollama import/pull workflow.')
    payload['files']={name+'.gguf':weights[0][1]}
    if licenses:payload['license']=licenses
    return payload,weights


def restore_cached(client, model, roots, endpoint=ENDPOINT, report=print):
    """Explicit setup/background recovery: copy cache over loopback, no download."""
    local_endpoint(endpoint)
    for root in roots:
        try:
            cached=cached_payload(root,model)
        except IncompleteCache:
            # A partial cache is not a usable import. Preserve it and inspect
            # the next store; explicit setup can resume the normal pull if none
            # is complete. Invalid descriptors/checksums still fail closed.
            report('Incomplete cached layers for '+model+'; preserved for resumable setup. Checking the next cache.')
            continue
        if cached is None:continue
        payload,weights=cached
        report('Restoring '+model+' from local cache '+str(root)+' into '+endpoint+'. No registry download.')
        for blob,digest in weights:
            response=client.head(endpoint+'/api/blobs/'+digest,timeout=(3,10))
            if response.status_code==404:
                # Ollama checks the full expected SHA-256 before accepting the
                # blob. Stream the file; keep RAM bounded and original bytes intact.
                with blob.open('rb') as source:
                    response=client.post(endpoint+'/api/blobs/'+digest,data=source,
                        headers={'Content-Type':'application/octet-stream'},timeout=(5,600))
                response.raise_for_status()
            else:response.raise_for_status()
        response=client.post(endpoint+'/api/create',json=payload,timeout=(3,120))
        response.raise_for_status()
        if response.json().get('status')!='success':raise ValueError('Cached model registration was not confirmed; inspect before retrying.')
        if model not in installed(client,endpoint):raise ValueError('Imported model is not visible after registration.')
        return True
    return False
