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
                if len(found)!=1:raise ValueError('Patch context must match exactly once; Read current source and use a unique hunk.')
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
        self.plan=json.loads((self.run/'validation-contract.json').read_text())
        self.allowed=set(request.get('allowed_paths') or [f['path'] for f in self.plan['files']])
        self.tests={row['path'] for row in self.plan['files'] if row['role']=='test'}
        self.fixed_tests={name:digest(self.root/name) for name in self.tests if (self.root/name).is_file()}

    def uncertain(self):
        path=self.run/'file-events.jsonl'
        if not path.exists():return False
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        attempted={row['signature'] for row in rows if row['stage']=='attempted'}
        applied={row['signature'] for row in rows if row['stage']=='applied'}
        return bool(attempted-applied)

    def protect(self, name):
        if name not in self.allowed:raise ValueError('Writes are limited to this worker assigned source files.')
        if name in self.fixed_tests:raise ValueError('Existing or already created test assertions are fixed. Repair the implementation, not the test.')

    def check_tests(self):
        # A test may appear after session startup through an external save. It
        # becomes fixed at our first observation too, never writable as "new".
        for name in self.tests:
            if name not in self.fixed_tests and (self.root/name).is_file():self.fixed_tests[name]=digest(self.root/name)
        if any(digest(self.root/name)!=sha for name,sha in self.fixed_tests.items()):
            raise UncertainCoding('Fixed test source changed; task stopped without replacing or replaying it.')

    def call(self, tool, args):
        with self.lock:
            if self.uncertain():raise UncertainCoding('An earlier save lacks confirmed readback; task stopped without replay.')
            self.check_tests()
            writing=tool in {'Write','Edit'}
            path=None;before=''
            if writing:
                path,_=decide(self.root,tool,args);name=path.relative_to(self.root).as_posix();self.protect(name)
                before=path.read_text(encoding='utf-8') if path.exists() else ''
            label={'Read':'Read','Glob':'Listed','Grep':'Searched','Write':'Created' if path and not path.exists() else 'Edited','Edit':'Edited','Plan':'Inspected plan'}[tool]
            item=Activity(self.report,self.run,'file' if writing else 'read',label+' '+str(args.get('file_path',args.get('pattern','plan'))),worker=self.worker)
            try:
                result=execute(tool,args,context=self)
                if writing:
                    result={**result,**review(before,path.read_text(encoding='utf-8'),name)}
                    if name in self.tests:self.fixed_tests[name]=digest(path)
                item.finish(**({k:result[k] for k in ('file','added','removed','diff') if k in result}),output=json.dumps(result,ensure_ascii=False)[:24000])
                return result
            except Exception as exc:
                item.finish('failed',output=str(exc)[:2000])
                if self.uncertain():raise UncertainCoding('Save outcome is uncertain; partial state retained without replay.') from exc
                raise

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
