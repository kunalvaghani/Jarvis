"""Durable no-replay guards for approved mailbox writes; no message text stored."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path


class Journal:
    def __init__(self,path,name,target):
        self.path,self.name,self.target=path,name,target
    def save(self,row):
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(row)+'\n')
        temporary.replace(self.path)
    def begin(self):
        self.save({'pending':True,'operation':self.name,'target':self.target})
    def accepted(self,result):
        # Retain the actual draft/message IDs even if the subsequent readback fails.
        self.save({'pending':True,'operation':self.name,'target':self.target,**self.identities(result)})
    def complete(self,result):
        self.save({'pending':False,'operation':self.name,'target':self.target,**self.identities(result)})
    def identities(self,result):
        drafts=self.name in {'gmail_api_draft','gmail_api_update_draft','gmail_api_delete_draft'}
        keys={'id':'draft_id' if drafts else 'message_id','draft_id':'draft_id','message_id':'message_id','ids':'message_ids'}
        return {keys[key]:result[key] for key in keys if key in result}


@contextmanager
def guard(base,name,value,args):
    fields={key:item for key,item in args.items() if key!='expected_sha256'}
    digest=hashlib.sha256(json.dumps([name,value,fields],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    root=Path(base)/'.jarvis-runtime/gmail-api/writes'
    root.mkdir(parents=True,exist_ok=True)
    if root.is_symlink():raise ValueError('Gmail write journal cannot use a linked directory.')
    path=root/(digest+'.json');lock_path=root/(digest+'.lock')
    if path.is_symlink() or lock_path.is_symlink():raise ValueError('Gmail write journal cannot use linked files.')
    with lock_path.open('a+b') as lock:
        lock.seek(0,2)
        if not lock.tell():lock.write(b'0');lock.flush()
        lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ValueError('This Gmail write is already owned by another request; no duplicate issued.') from None
        try:
            if path.exists() and json.loads(path.read_text()).get('pending'):
                raise ValueError('An earlier identical Gmail write has an uncertain outcome. Inspect the actual draft or message before another write; no action replayed.')
            yield Journal(path,name,value)
        finally:
            lock.seek(0)
            if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock,fcntl.LOCK_UN)
