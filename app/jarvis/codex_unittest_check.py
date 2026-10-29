"""Trusted unittest runner with bounded, read-only dependency failure facts.

Run as an absolute script with Python -I, then add the owned snapshot for normal
test discovery. Original tests, widgets, callbacks and assertions are unchanged.
Strings and object representations are never collected as runtime values.
"""
import argparse
import ast
import hashlib
import json
import math
import re
from pathlib import Path
import sys
import sysconfig
import traceback
import unittest


class OwnedCalls:
    """Main-thread source call facts only; never inspect locals or replace code."""
    def __init__(self,root,target,sources):
        self.sources={};self.current=None;self.anchor=None;self.phase=None
        self.rows={};self.seen_body=False;self.partial=False;self.target=str(target).casefold()
        try:
            if not isinstance(sources,dict) or len(sources)>32:raise ValueError()
            for name,sha in sources.items():
                path=(root/name).resolve(strict=True)
                if (Path(name).is_absolute() or not path.is_relative_to(root) or path==target or path.suffix!='.py'
                        or path.stat().st_size>80000 or not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{64}',sha)
                        or hashlib.sha256(path.read_bytes()).hexdigest()!=sha):raise ValueError()
                self.sources[str(path).casefold()]=(Path(name).as_posix(),sha)
        except (OSError,ValueError,TypeError):self.sources={}
    def start(self,test):
        self.current=type(test).__module__+'.'+type(test).__qualname__+'.'+test._testMethodName
        self.method=test._testMethodName;self.anchor=None;self.phase=None;self.rows={};self.seen_body=False;self.partial=False
    def stop(self):
        self.current=None;self.anchor=None;self.phase=None;self.rows={}
    def __call__(self,frame,event,arg):
        if self.current is None:return
        filename=frame.f_code.co_filename.casefold();function=frame.f_code.co_name
        if event=='call' and filename==self.target and function in {self.method,'setUp'}:
            self.anchor=frame;self.phase='test_body' if function==self.method else 'setup'
            if self.phase=='test_body':self.seen_body=True
            return
        if event=='return' and frame is self.anchor:
            self.anchor=None;self.phase=None;return
        if event!='call' or self.phase is None or filename not in self.sources:return
        if not re.fullmatch(r'[A-Za-z_]\w{0,79}|<lambda>',function):return
        name,sha=self.sources[filename];key=(self.phase,name,sha,function,frame.f_code.co_firstlineno)
        if key in self.rows:
            if self.rows[key]<10000:self.rows[key]+=1
            else:self.partial=True
        elif len(self.rows)<8:self.rows[key]=1
        else:self.partial=True
    def observation(self):
        return {'case_id':self.current,'test_body_seen':self.seen_body,
                'partial':self.partial or sys.getprofile() is not self,
                'scope':'Actual main-thread Python calls during setup/test body; no local values. Execution is not causal proof or acceptance.',
                'calls':[{'phase':key[0],'source_path':key[1],'source_sha256':key[2],'function':key[3],
                          'definition_line':key[4],'count':count} for key,count in self.rows.items()]}


def read_execution(data,root,outcomes):
    rows=data.get('owned_execution',[])
    if not outcomes or not isinstance(rows,list) or len(rows)>4 or len(json.dumps(rows))>6000:return []
    valid=[];failed=set(outcomes.get('failed_ids',[])+outcomes.get('error_ids',[]));seen=set()
    for row in rows:
        if (not isinstance(row,dict) or row.get('case_id') not in failed or row['case_id'] in seen
                or type(row.get('partial')) is not bool or type(row.get('test_body_seen')) is not bool
                or not isinstance(row.get('calls'),list) or len(row['calls'])>8):return []
        calls=[]
        for call in row['calls']:
            if not isinstance(call,dict):return []
            name=call.get('source_path');sha=call.get('source_sha256');function=call.get('function')
            if (not isinstance(name,str) or Path(name).is_absolute() or not name.endswith('.py')
                    or not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{64}',sha)
                    or not isinstance(function,str) or not re.fullmatch(r'[A-Za-z_]\w{0,79}|<lambda>',function)
                    or call.get('phase') not in {'setup','test_body'} or type(call.get('count')) is not int or not 1<=call['count']<=10000
                    or type(call.get('definition_line')) is not int or not 1<=call['definition_line']<=80000):return []
            path=(root/name).resolve(strict=True)
            if not path.is_relative_to(root) or path.stat().st_size>80000 or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:return []
            calls.append({key:call[key] for key in ('source_path','source_sha256','function','definition_line','count','phase')})
        seen.add(row['case_id']);valid.append({'case_id':row['case_id'],'partial':row['partial'],
            'test_body_seen':row['test_body_seen'],'calls':calls,'scope':'Verified snapshot-bound main-thread source calls, not causal proof or permissions.'})
    return valid


def scalar_operands(values, names):
    result={}
    for name in sorted(names)[:8]:
        if name not in values or len(name)>64:continue
        value=values[name];kind=type(value)
        if kind is str:result[name]={'type':'str'}
        elif kind is bool:result[name]={'type':'bool','value':value}
        elif value is None:result[name]={'type':'NoneType','value':None}
        elif kind is int:
            result[name]={'type':'int'}
            if abs(value)<=10**12:result[name]['value']=value
        elif kind is float:
            result[name]={'type':'float'}
            if math.isfinite(value) and abs(value)<=10**12:result[name]['value']=value
    return result


def observe_exception(error, method):
    """Observe only an actual trusted-stdlib statement in the failing traceback."""
    if isinstance(error[1],AssertionError):return None
    try:
        library=Path(sysconfig.get_path('stdlib')).resolve()
        frames=[];tb=error[2]
        while tb is not None and len(frames)<256:
            frames.append(tb);tb=tb.tb_next
        if tb is not None:return None
        for tb in reversed(frames):
            path=Path(tb.tb_frame.f_code.co_filename).resolve(strict=True)
            if path.suffix!='.py' or not path.is_relative_to(library):continue
            relative=path.relative_to(library)
            if any(p.casefold() in {'site-packages','dist-packages'} for p in relative.parts):continue
            if path.stat().st_size>512000:continue
            raw=path.read_bytes();tree=ast.parse(raw.decode('utf-8-sig'));line=tb.tb_lineno
            statements=[n for n in ast.walk(tree) if isinstance(n,ast.stmt)
                and not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))
                and n.lineno<=line<=n.end_lineno]
            if not statements:continue
            statement=min(statements,key=lambda n:n.end_lineno-n.lineno)
            operands=scalar_operands(tb.tb_frame.f_locals,{n.id for n in ast.walk(statement) if isinstance(n,ast.Name)})
            if not operands:continue
            return {'test_method':method[:120],'exception_type':error[0].__name__[:100],
                'frames':[{'module_path':relative.as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),
                    'line':line,'function':tb.tb_frame.f_code.co_name[:100],'operands':operands}],
                'partial':True,'scope':'Actual exception-frame scalar operands only; strings and objects omitted; untrusted diagnostic data, not permission.'}
    except (OSError,ValueError,SyntaxError,UnicodeError):pass
    return None


def read_evidence(path, root, test_path, test_sha256):
    if not path.is_file() or path.stat().st_size>16000:return {'observations':[],'outcomes':None}
    data=json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data,dict) or data.get('version')!=1 or data.get('root')!=str(root.resolve())
            or data.get('test_path')!=Path(test_path).as_posix() or data.get('test_sha256')!=test_sha256):return {'observations':[],'outcomes':None}
    observations=data.get('observations',[])
    if not isinstance(observations,list) or len(observations)>4 or len(json.dumps(observations))>3000:observations=[]
    outcomes=None;ids=data.get('passed_ids')
    if (isinstance(ids,list) and len(ids)<=32
            and all(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_.]{1,180}',name) for name in ids)
            and len(ids)==len(set(ids))
            and type(data.get('test_count')) is int and 0<=data['test_count']<=100000
            and type(data.get('successful')) is bool and type(data.get('skipped')) is int
            and 0<=data['skipped']<=100000 and type(data.get('outcomes_partial')) is bool):
        outcomes={'path':Path(test_path).as_posix(),'test_sha256':test_sha256,'test_count':data['test_count'],
                  'successful':data['successful'],'skipped':data['skipped'],
                  'passed_ids':ids,'partial':data['outcomes_partial']}
        kinds=[data.get(key) for key in ('failed_ids','error_ids')]
        if data.get('case_classifications_partial') is False and all(isinstance(group,list) and len(group)<=32
               and all(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_.]{1,180}',name) for name in group)
               and len(group)==len(set(group)) for group in kinds):
            combined=ids+kinds[0]+kinds[1]
            if len(combined)==len(set(combined)) and len(combined)+data['skipped']==data['test_count']:
                outcomes.update(failed_ids=kinds[0],error_ids=kinds[1])
    try:execution=read_execution(data,root,outcomes)
    except (OSError,ValueError,TypeError,KeyError,RecursionError):execution=[]
    return {'observations':observations,'outcomes':outcomes,'execution':execution}


def read_observations(path, root, test_path, test_sha256):
    return read_evidence(path,root,test_path,test_sha256)['observations']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--test',required=True)
    parser.add_argument('--facts',type=Path,required=True)
    parser.add_argument('--execution-sources',default='{}')
    args=parser.parse_args()
    root=args.root.resolve(strict=True);target=(root/args.test).resolve(strict=True)
    facts=args.facts.resolve()
    if (not target.is_relative_to(root) or target.suffix!='.py' or Path(args.test).is_absolute()
            or facts.parent!=root.parent or not facts.name.startswith('python-runtime-') or facts.suffix!='.json'):
        parser.error('Use one owned snapshot test and a fresh adjacent runtime evidence file')
    data={'version':1,'root':str(root),'test_path':Path(args.test).as_posix(),
          'test_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'observations':[],
          'passed_ids':[],'failed_ids':[],'error_ids':[],'outcomes_partial':False,'case_classifications_partial':False,'skipped':0}
    sources=json.loads(args.execution_sources) if len(args.execution_sources)<=12000 else {}
    tracker=OwnedCalls(root,target,sources)
    if tracker.sources:data['owned_execution']=[]
    class ObservedResult(unittest.TextTestResult):
        def startTest(self,test):
            super().startTest(test);tracker.start(test)
        def stopTest(self,test):
            tracker.stop();super().stopTest(test)
        def record_execution(self):
            if not tracker.sources:return
            row=tracker.observation()
            proposed=data['owned_execution']+[row]
            if len(proposed)<=4 and len(json.dumps(proposed))<=6000:data['owned_execution']=proposed
        def record_case(self,test,key):
            try:
                name=type(test).__module__+'.'+type(test).__qualname__+'.'+test._testMethodName
                count=len(data[key]) if key=='passed_ids' else len(data['failed_ids'])+len(data['error_ids'])
                partial='outcomes_partial' if key=='passed_ids' else 'case_classifications_partial'
                if count<32 and re.fullmatch(r'[A-Za-z0-9_.]{1,180}',name):data[key].append(name)
                else:data[partial]=True
            except (AttributeError,TypeError):data['outcomes_partial' if key=='passed_ids' else 'case_classifications_partial']=True
        def addSuccess(self,test):
            super().addSuccess(test)
            self.record_case(test,'passed_ids')
        def addFailure(self,test,error):
            self.record_execution()
            self.record_case(test,'failed_ids')
            super().addFailure(test,error)
        def addError(self,test,error):
            self.record_execution()
            # unittest may clear traceback locals while formatting the error.
            # Collect primitives first, never retain traceback/frame objects.
            fact=observe_exception(error,getattr(test,'_testMethodName',''))
            proposed=data['observations']+[fact] if fact else data['observations']
            if len(proposed)<=4 and len(json.dumps(proposed))<=3000:data['observations']=proposed
            self.record_case(test,'error_ids')
            super().addError(test,error)
    with facts.open('x',encoding='utf-8') as output:
        try:
            sys.path.insert(0,str(root))
            suite=unittest.defaultTestLoader.discover(str(target.parent),pattern=target.name)
            previous=sys.getprofile()
            try:
                if tracker.sources and previous is None:sys.setprofile(tracker)
                result=unittest.TextTestRunner(verbosity=2,resultclass=ObservedResult).run(suite)
            finally:
                if tracker.sources and previous is None:sys.setprofile(previous)
            data.update(test_count=result.testsRun,successful=result.wasSuccessful(),skipped=len(result.skipped))
            code=0 if result.wasSuccessful() else 1
        except BaseException as error:
            data.update(test_count=0,successful=False,startup_error_type=type(error).__name__,outcomes_partial=True)
            traceback.print_exc();code=1
        # Additional classifications must never crowd existing passed-case and
        # operand evidence beyond its original16KB reader bound.
        if 'owned_execution' in data and len(json.dumps(data,indent=2,allow_nan=False).encode('utf-8'))>16000:
            data['owned_execution']=[]
        if len(json.dumps(data,indent=2,allow_nan=False).encode('utf-8'))>16000:
            data['failed_ids']=[];data['error_ids']=[];data['case_classifications_partial']=True
        json.dump(data,output,indent=2,allow_nan=False)
    return code


if __name__=='__main__':
    raise SystemExit(main())
