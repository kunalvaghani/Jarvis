"""Native workspace tools using Jarvis's checked, non-replaying save boundary."""
import json
from pathlib import Path
import threading

from .coding_activity import Activity, review
from .codex_files import execute, digest
from .claude_code_guard import decide


class UncertainCoding(ValueError):
    """An attempted mutation lacks confirmed readback; stop the owned task."""


def patch_files(root, patch):
    """Parse bounded Add/Update patches with exact context; never guesses lines."""
    if not isinstance(patch,str) or len(patch)>240000:
        raise ValueError('Patch must be bounded text.')
    lines=patch.splitlines()
    if not lines or lines[0]!='*** Begin Patch' or lines[-1]!='*** End Patch':
        raise ValueError('Use *** Begin Patch and *** End Patch markers.')
    index=1;rows=[];seen=set()
    while index<len(lines)-1:
        header=lines[index];index+=1
        if header.startswith('*** Delete File:') or header.startswith('*** Move to:'):
            raise ValueError('Deletion/moving is not authorized by a source patch. Use explicit reviewed file operations.')
        if not header.startswith(('*** Add File: ','*** Update File: ')):
            raise ValueError('Expected Add File or Update File header.')
        adding=header.startswith('*** Add File: ');name=header.split(': ',1)[1]
        path,_=decide(root,'Read',{'file_path':name}) if not adding else decide(root,'Glob',{'path':name,'pattern':'*'})
        relative=path.relative_to(root).as_posix()
        if relative.casefold() in seen:raise ValueError('A patch may name each file once.')
        seen.add(relative.casefold())
        if adding and path.exists():raise ValueError('Add File already exists; Read then Update it.')
        if not adding and not path.is_file():raise ValueError('Update File is missing.')
        body=[]
        while index<len(lines)-1 and (not lines[index].startswith('*** ') or lines[index]=='*** End of File'):
            body.append(lines[index]);index+=1
        if adding:
            if not body or any(not line.startswith('+') for line in body):raise ValueError('Add File lines must start with +.')
            content='\n'.join(line[1:] for line in body)+'\n'
        else:
            content=path.read_text(encoding='utf-8');source=content.splitlines();cursor=0;hunks=[];old=[];new=[];at_end=False
            for line in body:
                if line.startswith('@@'):
                    if old or new:hunks.append((old,new,at_end))
                    old=[];new=[];at_end=False
                elif line=='*** End of File':at_end=True
                elif line.startswith((' ','-','+')):
                    if line[0] in ' -':old.append(line[1:])
                    if line[0] in ' +':new.append(line[1:])
                else:raise ValueError('Update hunk lines need context, + or - prefixes.')
            if old or new:hunks.append((old,new,at_end))
            if not hunks:raise ValueError('Update requires exact context hunks.')
            for old,new,at_end in hunks:
                if not old:raise ValueError('Update requires existing context; use Add for a new file.')
                found=[i for i in range(cursor,len(source)-len(old)+1) if source[i:i+len(old)]==old and (not at_end or i+len(old)==len(source))]
                if len(found)!=1:raise ValueError('Patch context must match exactly once; file: '+relative+'. Read current source and use a unique hunk.')
                at=found[0];source[at:at+len(old)]=new;cursor=at+len(new)
            content='\n'.join(source)+('\n' if content.endswith('\n') else '')
        decide(root,'Write',{'file_path':name,'content':content})
        for parent in (path,*path.parents):
            if parent==root:break
            if parent.is_symlink():raise ValueError('Linked source paths are outside the patch scope.')
        rows.append((relative,content))
    if not rows or len(rows)>16:raise ValueError('Patch needs one to sixteen source files.')
    return rows


class FileSession:
    def __init__(self, root, run, report=lambda *a:None, worker=''):
        self.root=Path(root).resolve(strict=True);self.run=Path(run).resolve(strict=True)
        self.reads={};self.lock=threading.RLock();self.report=report;self.worker=worker
        request=json.loads((self.run/'request.json').read_text())
        self.validation_goal=request.get('validation_goal',request.get('goal','')) or ''
        self.plan=json.loads((self.run/'validation-contract.json').read_text())
        self.allowed=set(request.get('allowed_paths') or [f['path'] for f in self.plan['files']])
        self.tests={row['path'] for row in self.plan['files'] if row['role']=='test'}
        self.fixed_tests={name:digest(self.root/name) for name in self.tests if (self.root/name).is_file()}
        from .codex_validation import preserved_named_files,source_path
        from .coder import project_files
        protected=preserved_named_files(self.validation_goal)
        self.preserved_names=protected
        self.fixed_sources={name:digest(source_path(self.root,name)) for name in project_files(self.root,limit=161)
                            if Path(name).name.casefold() in protected}

    def uncertain(self):
        path=self.run/'file-events.jsonl'
        if not path.exists():return False
        attempted=set();applied=set()
        try:
            if path.stat().st_size>8*2**20:raise ValueError('Journal exceeds limit.')
            with path.open(encoding='utf-8') as handle:
                for index,line in enumerate(handle):
                    if index>=4096 or len(line)>262144:raise ValueError('Journal exceeds limit.')
                    row=json.loads(line)
                    if not isinstance(row,dict):raise ValueError('Malformed journal row.')
                    stage=row.get('stage')
                    if stage in {'attempted','applied'}:
                        sig=row.get('signature')
                        if not isinstance(sig,str) or not sig:raise ValueError('Missing action signature.')
                        (attempted if stage=='attempted' else applied).add(sig)
                    elif stage!='rejected':raise ValueError('Unknown journal stage.')
        except (OSError,ValueError,UnicodeError,RecursionError) as exc:
            raise UncertainCoding('Save journal is damaged or exceeds limits; inspect fresh state before continuing.') from exc
        return bool(attempted-applied)

    def protect(self, name):
        if name not in self.allowed:raise ValueError('Writes are limited to this worker assigned source files.')
        if name in self.fixed_tests:raise ValueError('Existing or already created test assertions are fixed. Repair the implementation, not the test.')
        if Path(name).name.casefold() in self.preserved_names:raise ValueError('This source is explicitly preserved byte-for-byte. Read it as an input; do not rewrite it or add it as a generated output: '+name)

    def check_tests(self):
        # A test may appear after session startup through an external save. It
        # becomes fixed at our first observation too, never writable as "new".
        for name in self.tests:
            if name not in self.fixed_tests and (self.root/name).is_file():self.fixed_tests[name]=digest(self.root/name)
        if any(digest(self.root/name)!=sha for name,sha in self.fixed_tests.items()):
            raise UncertainCoding('Fixed test source changed; task stopped without replacing or replaying it.')
        if any(digest(self.root/name)!=sha for name,sha in self.fixed_sources.items()):
            raise UncertainCoding('Explicitly preserved source changed; task stopped without replacing or replaying it.')

    def pending_test_reads(self):
        if not any(not (self.root/name).exists() for name in self.tests):return []
        return sorted(f['path'] for f in self.plan['files']
            if f['role'] in {'logic','entrypoint','frontend','backend'} and (self.root/f['path']).is_file()
            and self.reads.get(str((self.root/f['path']).resolve()))!=digest(self.root/f['path']))

    def call(self, tool, args):
        with self.lock:
            if self.uncertain():raise UncertainCoding('An earlier save lacks confirmed readback; task stopped without replay.')
            self.check_tests()
            writing=tool in {'Write','Edit'}
            path=None;before=''
            if writing:
                path,_=decide(self.root,tool,args);name=path.relative_to(self.root).as_posix();self.protect(name)
                if tool=='Write' and name in self.tests and not path.exists():
                    unread=self.pending_test_reads()
                    if unread:raise ValueError('Before fixing new test assertions, Read the current existing implementation/protocol: '+json.dumps(unread)+'. Nothing saved.')
                    from .codex_validation import validate_test_draft
                    try:validate_test_draft(name,args.get('content',''),self.plan,self.validation_goal)
                    except (SyntaxError,ValueError) as error:
                        with (self.run/'test-draft-rejections.jsonl').open('a',encoding='utf-8') as output:
                            output.write(json.dumps({'path':name,'error':str(error),'proposed_source':args.get('content',''),'saved':False})+'\n')
                        raise ValueError(str(error)) from error
                from .engineering_judgment import proposed_file
                proposed_file(self.root, name)
                before=path.read_text(encoding='utf-8') if path.exists() else ''
            label={'Read':'Read','Glob':'Listed','Grep':'Searched','Write':'Created' if path and not path.exists() else 'Edited','Edit':'Edited','Plan':'Inspected plan'}[tool]
            item=Activity(self.report,self.run,'file' if writing else 'read',label+' '+str(args.get('file_path',args.get('pattern','plan'))),worker=self.worker)
            try:
                result=execute(tool,args,context=self)
                if writing:
                    result={**result,**review(before,path.read_text(encoding='utf-8'),name)}
                    from .engineering_judgment import reviewed_file
                    reviewed_file(self.root, name, before, path.read_text(encoding='utf-8'))
                    if name in self.tests:self.fixed_tests[name]=digest(path)
                item.finish(**({k:result[k] for k in ('file','added','removed','diff') if k in result}),output=json.dumps(result,ensure_ascii=False)[:24000])
                return result
            except Exception as exc:
                item.finish('failed',output=str(exc)[:2000])
                if self.uncertain():raise UncertainCoding('Save outcome is uncertain; partial state retained without replay.') from exc
                raise

    def edit_batch(self, args, *, render_members=None, rendering_callback=None, owned_methods=None, key_specific=None, literal_producer=None, function_contract=None):
        """One guarded save of a model-authored, non-overlapping statement batch."""
        from .codex_validation import source_path
        from .source_observation import exact_python_edit_spans
        with self.lock:
            if self.uncertain():raise UncertainCoding('An earlier save lacks confirmed readback; no batch replay.')
            self.check_tests()
            if set(args)!={'file_path','source_sha256','changes'}:raise ValueError('Batch requires file_path, source_sha256 and changes only.')
            path=source_path(self.root,args['file_path']);name=path.relative_to(self.root).as_posix();self.protect(name)
            if path.suffix!='.py' or not path.is_file() or path.stat().st_size>8000:raise ValueError('Batch requires one existing Python source up to8000 bytes.')
            current=digest(path)
            if args['source_sha256']!=current or self.reads.get(str(path.resolve()))!=current:
                raise ValueError('Read the current batch source and use its fresh raw SHA256; nothing saved.')
            compilations=[]
            if owned_methods:
                from .repair_contract import compile_owned_binding
                args,compilations=compile_owned_binding(args,owned_methods)
            if key_specific:
                if owned_methods:raise ValueError('Conflicting sealed interface strategies; no source saved.')
                from .repair_contract import compile_key_specific_binding
                args,compilations=compile_key_specific_binding(args,key_specific)
            content=path.read_text(encoding='utf-8');allowed=set(exact_python_edit_spans(content));changes=args['changes']
            if function_contract:
                from .execution_contract import function_spans,render,compile_definitions,compile_statements
                if owned_methods or key_specific or literal_producer or render_members:raise ValueError('Conflicting repair scopes; no source saved.')
                if function_contract['source_sha256']!=current:raise ValueError('Executed-function source changed; inspect fresh bytes.')
                test=function_contract['test_path']
                if self.fixed_tests.get(test)!=function_contract['test_sha256']:raise ValueError('Executed-function frozen binding changed.')
                if function_contract.get('statement_cells'):
                    updated,proof=compile_statements(content,args,function_contract)
                    if rendering_callback:rendering_callback(args,proof)
                    return self.call('Write',{'file_path':name,'content':updated})
                selected=function_spans(content,list(allowed),function_contract['functions'])
                if not selected:raise ValueError('Executed-function spans changed; no source saved.')
                args=compile_definitions(args,function_contract,selected)
                args,proof=render(args,function_contract);changes=args['changes']
                if rendering_callback:rendering_callback(args,proof)
            if literal_producer:
                from .key_producer import producer,validate_replacement
                fresh=producer(content,list(allowed),[literal_producer['member']],literal_producer['missing_key'])
                if fresh!=literal_producer:raise ValueError('Producer provenance changed; no source saved.')
                if not isinstance(changes,list) or len(changes)!=1 or changes[0].get('old_string')!=fresh['old_string']:
                    raise ValueError('Producer repair requires its single exact literal declaration.')
                validate_replacement(changes[0]['old_string'],changes[0].get('new_string',''),fresh)
            if not isinstance(changes,list) or not 1<=len(changes)<=4:raise ValueError('Batch requires1–4 bounded statement changes.')
            spans=[];total=0
            for row in changes:
                if not isinstance(row,dict) or set(row)!={'old_string','new_string'}:raise ValueError('Each batch change requires old_string/new_string only.')
                old=row['old_string'];new=row['new_string']
                if not isinstance(old,str) or not isinstance(new,str) or old not in allowed or content.count(old)!=1:
                    raise ValueError('Batch old_string must be an exact unique current statement.')
                if old==new or len(new)>1200:raise ValueError('Batch changes must differ and use at most1200 replacement characters each.')
                total+=len(new);start=content.index(old);spans.append((start,start+len(old),new))
            if total>2400:raise ValueError('Batch replacement total exceeds2400 characters; nothing saved.')
            spans.sort()
            if any(left[1]>right[0] for left,right in zip(spans,spans[1:])):raise ValueError('Batch statements overlap; nothing saved.')
            if render_members:
                from .repair_contract import render_bindings
                rendered,provenance=render_bindings(args,render_members)
                if rendering_callback:rendering_callback(rendered,compilations+provenance)
                spans=sorted((content.index(row['old_string']),content.index(row['old_string'])+len(row['old_string']),row['new_string'])
                             for row in rendered['changes'])
            for start,end,new in reversed(spans):content=content[:start]+new+content[end:]
            # Write performs the original syntax/interface, candidate, scope,
            # fresh-read, atomic journal and readback checks exactly once.
            return self.call('Write',{'file_path':name,'content':content})

    def patch(self, patch):
        with self.lock:
            rows=patch_files(self.root,patch)
            for name,content in rows:
                self.protect(name)
                if (self.root/name).exists() and self.reads.get(str((self.root/name).resolve()))!=digest(self.root/name):
                    raise ValueError('Read every existing patched file before applying the patch.')
            # All syntax, paths and current-read guards pass before the first save.
            rows.sort(key=lambda row:row[0] not in self.tests)
            saved=[]
            try:
                for name,content in rows:saved.append(self.call('Write',{'file_path':name,'content':content}))
            except Exception as exc:
                if saved:raise UncertainCoding('Patch stopped after confirmed partial saves; inspect fresh state before continuing. Patch was not replayed.') from exc
                raise
            return {'saved':saved,'checks':'Exact patch and atomic source readback; runtime checks still required.'}

    def changed(self):
        path=self.run/'file-events.jsonl'
        if not path.exists():return []
        return sorted({Path(row['path']).relative_to(self.root).as_posix() for row in map(json.loads,path.read_text().splitlines()) if row['stage']=='applied'})
