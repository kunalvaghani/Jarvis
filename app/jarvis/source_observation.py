"""Bounded source facts for diagnosis; never executes or changes project code."""
import ast
import hashlib
import json
import re


PYTHON_OBJECT_PROTOCOL_REFERENCE={
    'checked_on':'2026-10-27',
    'facts':'Dictionary values may be arbitrary objects; values need not share one concrete type. User-defined classes can provide methods and customize item access through __getitem__.',
    'engineering_inference':'Failure of two concrete representations does not prove a combined interface impossible. Assess permitted owned implementations without changing frozen tests or library classes.',
    'sources':['https://docs.python.org/3.10/library/stdtypes.html#mapping-types-dict',
               'https://docs.python.org/3.10/reference/datamodel.html#special-method-names']}


def receiver_protocols(tree, module_for):
    """Group coexisting indexed call shapes; no runtime type or repair inferred.

    Stay conservative when test classes or instance assignments are ambiguous.
    The caller supplies existing owned-module provenance, never permissions.
    """
    classes=[node for node in ast.walk(tree) if isinstance(node,ast.ClassDef)]
    if len(classes)!=1 or len(classes[0].name)>80:return {}
    cls=classes[0]
    methods=[node for node in cls.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
             and node.args.args and not any(isinstance(d,ast.Name) and d.id in {'staticmethod','classmethod'} for d in node.decorator_list)]
    instances={node.args.args[0].arg for node in methods}
    def instance_field(node):
        if not isinstance(node,ast.Attribute):return False
        while isinstance(node,ast.Attribute):node=node.value
        return isinstance(node,ast.Name) and node.id in instances
    assigned={}
    for node in ast.walk(cls):
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if instance_field(target):assigned.setdefault(ast.unparse(target),set()).add(ast.dump(node.value))
    if any(len(values)>1 for values in assigned.values()):return {}
    groups={}
    for method in methods:
        # Nested scopes may shadow instance names; do not merge those receivers.
        if any(isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n is not method for n in ast.walk(method)):continue
        for node in ast.walk(method):
            if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute):continue
            receiver=node.func.value;depth=0
            while isinstance(receiver,ast.Subscript):depth+=1;receiver=receiver.value
            if depth>4 or not instance_field(receiver):continue
            module=module_for(receiver)
            if not module:continue
            owner=ast.unparse(receiver);call=ast.unparse(node)
            if len(owner)>120 or len(node.func.attr)>80 or len(call)>220:continue
            key=(module,owner,node.func.attr)
            # A single example per depth loses per-key obligations: two keys
            # at the same depth may require different values from a third key.
            groups.setdefault(key,{}).setdefault(depth,{}).setdefault(call,{'line':node.lineno,'call':call})
    result={}
    for (module,owner,method),observations in groups.items():
        if len(observations)<2:continue
        depths=sorted(observations)
        all_rows=[row for depth in depths for row in observations[depth].values()]
        # Keep every depth represented before filling the bounded remainder.
        selected=[next(iter(observations[depth].values())) for depth in depths]
        for row in sorted(all_rows,key=lambda row:row['line']):
            if row not in selected and len(selected)<8:selected.append(row)
        selected.sort(key=lambda row:row['line'])
        result.setdefault(module,[]).append({'test_class':cls.name,'receiver':owner,'method':method,
            'access_depths':depths,'observations':selected,
            'distinct_call_count':len(all_rows),'observations_partial':len(selected)<len(all_rows)})
        if sum(len(rows) for rows in result.values())>=8:break
    return result


def member_assignment_observations(content, members, limit=6, budget=800):
    """Bounded same-named instance writes and unique local value definitions.

    These are static source facts, not runtime alias/type claims or repairs.
    Parse only; never import or evaluate the observed module.
    """
    if not isinstance(content,str) or len(content)>80000:return []
    if not isinstance(members,set) or not members or len(members)>8:return []
    try:tree=ast.parse(content)
    except (SyntaxError,ValueError):return []
    result=[];seen=set();examined=0
    for cls in tree.body:
        if not isinstance(cls,ast.ClassDef):continue
        for method in cls.body:
            if not isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)) or not method.args.args:continue
            if any(isinstance(d,ast.Name) and d.id in {'staticmethod','classmethod'} for d in method.decorator_list):continue
            if any(isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n is not method for n in ast.walk(method)):continue
            instance=method.args.args[0].arg;locals_={};primary=[]
            for node in ast.walk(method):
                if not isinstance(node,(ast.Assign,ast.AnnAssign)) or node.value is None:continue
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target,ast.Name):locals_.setdefault(target.id,[]).append(node)
                    while isinstance(target,ast.Subscript):target=target.value
                    if (isinstance(target,ast.Attribute) and target.attr in members
                            and isinstance(target.value,ast.Name) and target.value.id==instance):primary.append(node)
            pending=[(node,0,'member_write') for node in primary]
            while pending:
                node,depth,role=pending.pop(0)
                if node.lineno in seen:continue
                if examined>=24 or len(result)>=limit:return result
                examined+=1
                seen.add(node.lineno);snippet=ast.get_source_segment(content,node)
                if snippet and len(snippet)<=240 and len(cls.name)<=80 and len(method.name)<=80:
                    row={'class':cls.name,'method':method.name,'line':node.lineno,'source':snippet,'kind':role}
                    if len(result)<limit and len(json.dumps(result+[row],ensure_ascii=False))<=budget:result.append(row)
                if depth<2:
                    for ref in ast.walk(node.value):
                        candidates=locals_.get(ref.id,[]) if isinstance(ref,ast.Name) else []
                        if len(candidates)==1:pending.append((candidates[0],depth+1,'unique_local_definition'))
    return result


def outline(content, limit=16):
    try:tree=ast.parse(content)
    except (SyntaxError,ValueError):return []
    rows=[]
    for node in ast.walk(tree):
        if not isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) or len(node.name)>80:continue
        row={'name':node.name,'start':node.lineno,'end':node.end_lineno}
        if len(json.dumps(rows+[row]))<=800:rows.append(row)
        if len(rows)>=limit:break
    return rows


def exact_python_edit_spans(content, limit=32, budget=6000):
    """Bounded unique physical source spans, never inferred replacements.

    This only parses owned Python text. Whole long functions/classes are not
    offered. Each span contains one complete statement and matches exactly once.
    """
    import textwrap
    if not isinstance(content,str) or len(content)>8000:return []
    try:tree=ast.parse(content)
    except (SyntaxError,ValueError):return []
    lines=content.splitlines(keepends=True);rows=[]
    nodes=sorted(ast.walk(tree),key=lambda node:(getattr(node,'lineno',0),getattr(node,'col_offset',0)))
    # Prefix-only statement inventories can make later handlers unreachable.
    # Reserve complete small function/method spans first, within the same
    # count/byte budget; repeated inner statements then have a unique anchor.
    symbols=[node for node in nodes if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
             and getattr(node,'end_lineno',node.lineno)-node.lineno<64 and not node.decorator_list]
    for node in symbols+[node for node in nodes if node not in symbols]:
        if not isinstance(node,ast.stmt) or not hasattr(node,'end_lineno'):continue
        symbol=node in symbols
        if (not symbol and node.end_lineno-node.lineno>=6) or getattr(node,'decorator_list',None):continue
        if lines[node.lineno-1][:node.col_offset].strip():continue
        span=''.join(lines[node.lineno-1:node.end_lineno]).rstrip('\r\n')
        if not span or len(span)>(2400 if symbol else 400) or span in rows or content.count(span)!=1:continue
        try:
            if len(ast.parse(textwrap.dedent(span)).body)!=1:continue
        except (SyntaxError,ValueError):continue
        if sum(map(len,rows))+len(span)>budget:continue
        rows.append(span)
        if len(rows)>=limit:break
    return rows


def stdlib_failure_window(frames):
    """Quote a small installed-library failure site, never an arbitrary path.

    Only existing Python sources resolved beneath this interpreter's standard
    library qualify. Third-party packages and project sources are excluded.
    No modules are imported or executed to obtain these read-only facts.
    """
    import sysconfig
    from pathlib import Path
    library=Path(sysconfig.get_path('stdlib')).resolve()
    for name,line in reversed(frames[-3:]):
        try:
            path=Path(name).resolve(strict=True)
            if path.suffix!='.py' or not path.is_relative_to(library):continue
            relative=path.relative_to(library)
            if any(part.casefold() in {'site-packages','dist-packages'} for part in relative.parts):continue
            if path.stat().st_size>512000:continue
            raw=path.read_bytes();lines=raw.decode('utf-8-sig').splitlines();line=int(line)
            if not 1<=line<=len(lines):continue
            start=max(1,line-2)
            source='\n'.join(f'{index}: {lines[index-1]}' for index in range(start,min(len(lines),line+2)+1))
            return {'module_path':relative.as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),
                    'failure_line':line,'start':start,'numbered_source':source[:500],
                    'partial':True,'source_truncated':len(source)>500,
                    'scope':'Installed standard-library source at the primary traceback; read-only evidence, no repair or permission inferred.'}
        except (OSError,ValueError,UnicodeError):continue
    return None


def failure_context(error, files=None):
    """Prefer an actual exception; quote frozen tests and trusted stdlib only."""
    text=str(error.get('error',''))
    matches=list(re.finditer(r'^(?:[\w.]*Error|Exception): [^\r\n]+',text,re.M))
    if not matches:return None
    primary=next((m for m in matches if not m.group().startswith('AssertionError:')),matches[0])
    data={'primary_error':primary.group()[:240],'primary_error_partial':len(primary.group())>240}
    headers=list(re.finditer(r'^(?:FAIL|ERROR): (test_\w+)\b(?:\s+\(([^)\r\n]+)\))?',text[:primary.start()],re.M))
    start=headers[-1].start() if headers else max(0,text.rfind('Traceback (most recent call last):',0,primary.start()))
    frames=re.findall(r'File "([^"\r\n]+)", line (\d+)',text[start:primary.start()])
    basename=lambda value:value.replace('\\','/').rsplit('/',1)[-1]
    data['source_locations']=[{'file':basename(name),'line':int(line)} for name,line in frames[-3:]]
    library_window=stdlib_failure_window(frames)
    if library_window:
        data['installed_stdlib_source']=library_window
        method=headers[-1].group(1) if headers else None
        observations=error.get('runtime_failure_facts',[])
        for row in observations[:4] if isinstance(observations,list) else []:
            if (not isinstance(row,dict) or row.get('test_method')!=method
                    or row.get('exception_type')!=primary.group().split(':',1)[0].rsplit('.',1)[-1]):continue
            rows=row.get('frames',[])
            for observed in rows[:1] if isinstance(rows,list) else []:
                if (not isinstance(observed,dict) or observed.get('module_path')!=library_window['module_path']
                        or observed.get('sha256')!=library_window['sha256'] or observed.get('line')!=library_window['failure_line']):continue
                values=observed.get('operands',{});safe={}
                if not isinstance(values,dict):continue
                import math
                for name,value in list(values.items())[:8]:
                    if not isinstance(name,str) or len(name)>64 or not isinstance(value,dict):continue
                    kind=value.get('type');actual=value.get('value')
                    if kind not in {'str','int','float','bool','NoneType'}:continue
                    safe[name]={'type':kind}
                    if (kind=='int' and type(actual) is int and abs(actual)<=10**12
                            or kind=='float' and type(actual) is float and math.isfinite(actual) and abs(actual)<=10**12
                            or kind=='bool' and type(actual) is bool
                            or kind=='NoneType' and actual is None):safe[name]['value']=actual
                if safe:
                    library_window['observed_operands']=safe
                    library_window['operand_evidence']='Actual failing unittest traceback; matching test method, exception type, library hash and line. Strings and objects omitted.'
    if files is None or error.get('path') not in files.tests:return data
    if not headers:return data
    method=headers[-1].group(1)
    owner=headers[-1].group(2)
    from .codex_validation import source_path
    try:
        path=source_path(files.root,error['path'])
        if path.suffix!='.py' or not path.is_file() or path.stat().st_size>80000:return data
        content=path.read_text(encoding='utf-8');tree=ast.parse(content)
    except (OSError,ValueError,SyntaxError,UnicodeError):return data
    candidates=ast.walk(tree)
    if owner:
        classes=[node for node in ast.walk(tree) if isinstance(node,ast.ClassDef) and node.name==owner.rsplit('.',1)[-1]]
        candidates=[node for cls in classes for node in cls.body]
    for node in candidates:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==method:
            data.update(test_method=method,test_line=node.lineno)
            for name,line in reversed(frames):
                line=int(line)
                if basename(name).casefold()!=basename(error['path']).casefold() or not node.lineno<=line<=node.end_lineno:continue
                data['failure_line']=line
                statements=[item for item in ast.walk(node) if isinstance(item,ast.stmt)
                            and not isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))
                            and item.lineno<=line<=item.end_lineno]
                if statements:
                    statement=min(statements,key=lambda item:item.end_lineno-item.lineno)
                    source=ast.get_source_segment(content,statement)
                    if source:
                        data['failed_statement']=source[:400]
                        data['failed_statement_partial']=len(source)>400
                break
            source=ast.get_source_segment(content,node)
            if source and len(source)<=1200:data['frozen_test_source']=source
            break
    return data


def prior_failure_observations(validations, current, files=None, budget=1200):
    """Earlier distinct failures under the same frozen checks, never instructions.

    Source fingerprints identify recorded validation inputs. Stale test versions
    cannot supply statement quotes for the current immutable contract.
    """
    def observations(value):
        hashes=value.get('hashes',{})
        if not hashes:return []
        fingerprint=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
        rows=[]
        for error in value.get('errors',[])[:3]:
            name=error.get('path','')
            frozen=files is not None and name in files.tests
            expected=current.get('hashes',{}).get(name)
            if frozen and (not expected or hashes.get(name)!=expected):continue
            context=failure_context(error,files)
            if not context:continue
            row={'check':name[:160],'primary_error':context['primary_error'][:160],
                 'source_fingerprint':fingerprint}
            if value.get('candidate_only') is True:row['candidate_only']=True
            if isinstance(value.get('date'),str):row['validation_date']=value['date'][:80]
            if len(name)>160:row['check_partial']=True
            if len(context['primary_error'])>160 or context.get('primary_error_partial'):row['error_partial']=True
            if frozen:row['frozen_test_sha256']=expected
            for field in ('failure_line','failed_statement'):
                if field in context:row[field]=context[field][:220] if isinstance(context[field],str) else context[field]
            if len(context.get('failed_statement',''))>220 or context.get('failed_statement_partial'):
                row['failed_statement_partial']=True
            rows.append(row)
        return rows
    def key(row):
        return (row['check'],row['primary_error'],row.get('failure_line'),row.get('failed_statement'))
    active={key(row) for row in observations(current)}
    previous={}
    for value in validations[-8:]:
        for row in observations(value):
            identity=key(row)
            if identity in active:continue
            previous.pop(identity,None)
            previous[identity]=row
    rows=list(previous.values())[-3:]
    while len(json.dumps(rows,ensure_ascii=False))>budget and rows:rows.pop(0)
    return rows


def diagnostic_windows(files, turns, focus, count=24, budget=2400):
    """Allow at most two complementary slices after the first bounded read.

    The three-read allowance counts consecutive successful slices. Coverage
    also retains earlier same-hash slices across rejected repairs, so recovery
    cannot repeatedly offer the same views. Excerpts are fresh facts,
    not a replacement implementation or a claim that checks passed.
    """
    if not turns:return None
    last=turns[-1];name=last.get('arguments',{}).get('file_path')
    if name not in focus or name not in files.allowed or name in files.fixed_sources:return None
    windows=[];observed_hashes=[]
    for row in reversed(turns):
        args=row.get('arguments',{});result=row.get('result')
        if row.get('tool')!='read_slice' or args.get('file_path')!=name:break
        if not isinstance(result,dict) or result.get('error') or not result.get('lines'):break
        rows=result['lines']
        start=rows[0]['line'] if isinstance(rows[0],dict) and isinstance(rows[0].get('line'),int) else args.get('start',1)
        windows.append((max(1,int(start)),len(rows)))
        observed_hashes.append(result.get('sha256'))
    if not windows:return None
    from .codex_validation import source_path
    try:
        path=source_path(files.root,name)
        if path.suffix!='.py' or not path.is_file() or path.stat().st_size>80000:return None
        raw=path.read_bytes();content=raw.decode('utf-8');tree=ast.parse(content)
    except (OSError,ValueError,SyntaxError,UnicodeError):return None
    sha256=hashlib.sha256(raw).hexdigest()
    if any(value and value!=sha256 for value in observed_hashes):return None
    coverage=[]
    for row in turns[-128:]:
        args=row.get('arguments',{});result=row.get('result')
        if row.get('tool')!='read_slice' or args.get('file_path')!=name:continue
        if not isinstance(result,dict) or result.get('error') or result.get('sha256')!=sha256:continue
        observed=result.get('lines')
        if not isinstance(observed,list) or not observed:continue
        indices=[item.get('line') for item in observed if isinstance(item,dict)]
        if len(indices)!=len(observed) or any(type(index) is not int or index<1 for index in indices):continue
        coverage.extend(indices)
    # Current successful slices without hash metadata retain the existing
    # consecutive-window behavior, but never contribute historical coverage.
    for start,size in windows:coverage.extend(range(start,start+size))
    coverage=set(coverage)
    lines=content.splitlines();starts={1};spans=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            spans.append((node.lineno,node.end_lineno))
            starts.update(range(node.lineno,node.end_lineno+1,count))
            starts.update(line for line in range(node.lineno,node.end_lineno+1)
                          if line not in coverage and line-1 in coverage)
    def window_end(start):
        containing=[end for first,end in spans if first<=start<=end]
        return min(start+count,len(lines)+1,min(containing)+1 if containing else len(lines)+1)
    novelty={start:sum(line not in coverage for line in range(start,window_end(start)))
             for start in starts if start<=len(lines)}
    most_new=max(novelty.values(),default=0)
    choices=sorted(start for start,new in novelty.items() if new and new==most_new)[:128]
    excerpts=[{'start':start,'lines':[f'{i+1}: {lines[i]}' for i in range(start-1,min(start+size-1,len(lines)))],
               'partial':True} for start,size in reversed(windows[:3])]
    data={'file_path':name,'sha256':sha256,
          'starts':choices if len(windows)<3 else [],'count':count,'reads_used':len(windows),
          'symbols':outline(content),'windows':excerpts}
    while len(json.dumps(data,ensure_ascii=False))>budget and any(row['lines'] for row in excerpts):
        max(excerpts,key=lambda row:sum(len(line) for line in row['lines']))['lines'].pop()
    for field in ('symbols','starts'):
        while len(json.dumps(data,ensure_ascii=False))>budget and data[field]:data[field].pop()
    return data
