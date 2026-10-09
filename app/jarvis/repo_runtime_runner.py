"""Trusted one-shot Linux container entry point; never used as a host executor."""
import asyncio
import base64
import contextlib
import ctypes
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import platform
import sys
import enum
import typing
import types


def harden():
    import resource
    if sys.platform!='linux' or platform.machine()!='x86_64':raise RuntimeError('Only tested Linux x86_64 seccomp execution is supported.')
    if os.geteuid()==0:raise RuntimeError('Repository execution must not run as root.')
    # Enforce observed cgroup/mount limits, not only Docker command intentions.
    cgroup=Path('/sys/fs/cgroup')
    if int((cgroup/'memory.max').read_text())>256*1024*1024 or int((cgroup/'pids.max').read_text())>16:
        raise RuntimeError('Container memory/PID bounds are not enforced.')
    quota,period=(cgroup/'cpu.max').read_text().split()
    if quota=='max' or int(quota)/int(period)>.51:raise RuntimeError('Container CPU quota is not enforced.')
    mounts={row.split()[4]:row.split()[5].split(',') for row in Path('/proc/self/mountinfo').read_text().splitlines()}
    if any('ro' not in mounts.get(name,[]) for name in ('/','/source','/runner.py')) or 'noexec' not in mounts.get('/work',[]):
        raise RuntimeError('Required read-only mounts or noexec scratch boundary are absent.')
    resource.setrlimit(resource.RLIMIT_AS,(192*1024*1024,192*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(5,5));resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    class Filter(ctypes.Structure):
        _fields_=[('code',ctypes.c_ushort),('jt',ctypes.c_ubyte),('jf',ctypes.c_ubyte),('k',ctypes.c_uint)]
    class Program(ctypes.Structure):
        _fields_=[('len',ctypes.c_ushort),('filter',ctypes.POINTER(Filter))]
    # Verify architecture and reject the x32 syscall namespace; then deny process
    # execution, forking, namespace/privilege attacks and network entry points.
    rules=[(0x20,0,0,4),(0x15,1,0,0xc000003e),(0x06,0,0,0x80000000),
           (0x20,0,0,0),(0x45,0,1,0x40000000),(0x06,0,0,0x80000000)]
    for number in (59,322,56,435,57,58,42,49,50,43,288,101,308,272,165,166,304,321,323,310,311,298,250,248,249):
        rules.extend([(0x15,0,1,number),(0x06,0,0,0x00050001)])
    # asyncio requires an AF_UNIX socketpair. Internet socket creation stays denied.
    for number in (41,53):
        rules.extend([(0x15,0,4,number),(0x20,0,0,16),(0x15,1,0,1),
                      (0x06,0,0,0x00050001),(0x06,0,0,0x7fff0000)])
    rules.append((0x06,0,0,0x7fff0000))
    array=(Filter*len(rules))(*(Filter(*r) for r in rules));program=Program(len(rules),array)
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(38,1,0,0,0)!=0 or libc.prctl(22,2,ctypes.byref(program),0,0)!=0:
        raise RuntimeError('Kernel syscall isolation could not be installed.')


def converted(value, hint):
    if isinstance(hint,type) and issubclass(hint,enum.Enum):return hint(value)
    origin=typing.get_origin(hint);args=typing.get_args(hint)
    if origin in (list,tuple,set) and args:
        return origin(converted(v,args[min(i,len(args)-1)] if origin is tuple and args[-1] is not Ellipsis else args[0]) for i,v in enumerate(value))
    if origin is dict and len(args)==2:return {converted(k,args[0]):converted(v,args[1]) for k,v in value.items()}
    if origin in (typing.Union,types.UnionType):
        for candidate in args:
            if isinstance(candidate,type) and issubclass(candidate,enum.Enum):
                try:return candidate(value)
                except (ValueError,TypeError):pass
    return value


def bind(function, supplied):
    signature=inspect.signature(function)
    # Annotation evaluation is confined to this already isolated, approved process.
    try:hints=typing.get_type_hints(function.__init__ if inspect.isclass(function) else function)
    except (NameError,TypeError):hints={}
    supplied=dict(supplied)
    for name,param in signature.parameters.items():
        if name not in supplied:continue
        if param.kind==param.VAR_POSITIONAL:supplied[name]=[converted(v,hints.get(name)) for v in supplied[name]]
        elif param.kind==param.VAR_KEYWORD:supplied[name]={k:converted(v,hints.get(name)) for k,v in supplied[name].items()}
        else:supplied[name]=converted(supplied[name],hints.get(name))
    pos=[];keywords={}
    has_varargs=any(p.kind==p.VAR_POSITIONAL for p in signature.parameters.values())
    for name,param in signature.parameters.items():
        if param.kind==param.POSITIONAL_ONLY or (has_varargs and param.kind==param.POSITIONAL_OR_KEYWORD):
            if name in supplied:pos.append(supplied[name])
            elif param.default is not param.empty:pos.append(param.default)
            else:raise TypeError('Missing positional argument: '+name)
        elif param.kind==param.VAR_POSITIONAL:pos.extend(supplied.get(name,[]))
        elif param.kind==param.VAR_KEYWORD:keywords.update(supplied.get(name,{}))
        elif name in supplied:keywords[name]=supplied[name]
    signature.bind(*pos,**keywords)
    return function(*pos,**keywords)


def serializable(value,depth=0):
    if depth>12:raise ValueError('Result nesting budget exceeded.')
    if value is None or type(value) in (str,int,float,bool):return value
    if isinstance(value,bytes):return {'encoding':'base64','data':base64.b64encode(value).decode()}
    if isinstance(value,dict):
        if len(value)>1000 or not all(isinstance(k,str) for k in value):raise ValueError('Result object exceeds supported JSON contract.')
        return {k:serializable(v,depth+1) for k,v in value.items()}
    if isinstance(value,(list,tuple,set)):
        if len(value)>1000:raise ValueError('Result collection exceeds budget.')
        return [serializable(v,depth+1) for v in value]
    if inspect.isgenerator(value):
        rows=[]
        for item in value:
            if len(rows)>=1000:raise ValueError('Generator result exceeds budget.')
            rows.append(serializable(item,depth+1))
        return rows
    return {'python_type':type(value).__module__+'.'+type(value).__qualname__,'display':str(value)[:2000]}


class BoundedOutput(io.TextIOBase):
    def write(self,value):return len(value)  # Repository stdout/stderr is not a protocol or audit log.


def main():
    try:
        raw=sys.stdin.buffer.read(16001)
        if len(raw)>16000:raise ValueError('Request exceeds JSON input budget.')
        request=json.loads(raw)
        harden()
        os.environ.clear()
        if request.get('probe'):
            value={'isolated':True,'uid':os.geteuid(),'machine':platform.machine(),'cgroups_verified':True,'mounts_verified':True,'seccomp_installed':True}
        else:
            entity=request['entity'];root=Path('/source')/entity['import_root']
            sys.path.insert(0,str(root))
            with contextlib.redirect_stdout(BoundedOutput()),contextlib.redirect_stderr(BoundedOutput()):
                module=importlib.import_module(entity['module'])
                parts=entity['symbol'].split('.');target=getattr(module,parts[0]);arguments=request['arguments']
                if entity['kind']=='method':
                    target=bind(target,arguments['constructor']);target=getattr(target,parts[1]);arguments=arguments['arguments']
                elif len(parts)==2:target=getattr(target,parts[1])
                value=bind(target,arguments)
                if inspect.isawaitable(value):value=asyncio.run(value)
                value=serializable(value)
        response={'ok':True,'value':value}
        text=json.dumps(response,allow_nan=False)
        if len(text.encode())>32000:raise ValueError('Result exceeds 32KB JSON output budget.')
    except BaseException as error:
        text=json.dumps({'ok':False,'error_type':type(error).__name__,'error':str(error)[:500]})
    print(text,flush=True)


if __name__=='__main__':main()
