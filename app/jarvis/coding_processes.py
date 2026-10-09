"""Owned command sessions, bounded polling and actual console activity."""
from pathlib import Path
import os
import re
import subprocess
import time
from uuid import uuid4

from .coding_activity import Activity
from .coding_activity import emit
from .coding_files import UncertainCoding
from .coding_programs import checked_argv
from .harness_process import OwnedJob, hidden_spawn


class Processes:
    def __init__(self, root, run, report, cancelled=lambda:False, worker=''):
        self.root=Path(root);self.run=Path(run);self.report=report
        self.cancelled=cancelled;self.worker=worker;self.sessions={};self.uncertain=False

    def start(self, argv, workdir='.', yield_time_ms=1000, timeout_seconds=90, trusted=False, resolved=False):
        if self.uncertain: raise UncertainCoding('A command outcome was uncertain; no new command was started.')
        if self.cancelled(): raise ValueError('Stopped before starting command.')
        cwd=(self.root/workdir).resolve(strict=True)
        if not cwd.is_relative_to(self.root.resolve()) or not cwd.is_dir(): raise ValueError('Working directory must be inside this project.')
        if len(self.sessions)>=4: raise ValueError('Poll existing owned sessions before creating more.')
        argv=argv if trusted or resolved else checked_argv(cwd,argv)
        key=uuid4().hex;job=OwnedJob();output_path=self.run/('command-'+key+'.log');output=output_path.open('wb')
        activity=Activity(self.report,self.run,'command','Running '+Path(argv[0]).name,
                          subprocess.list2cmdline(argv),self.worker)
        try:
            environment=dict(os.environ) if trusted else {k:v for k,v in os.environ.items() if not re.search(r'(?:TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY|AUTH_TOKEN|(?:^|_)KEY$|^(?:HTTP|HTTPS|ALL)_PROXY$)',k,re.I)
                         and not k.upper().startswith(('OPENAI_','ANTHROPIC_','CLAUDE_','AWS_','AZURE_','GOOGLE_','GIT_','CODEX_'))}
            environment.update(GIT_TERMINAL_PROMPT='0',GIT_OPTIONAL_LOCKS='0',GOPROXY='off',GOTOOLCHAIN='local',GOSUMDB='off')
            process=hidden_spawn(job,subprocess.Popen)(argv,cwd=cwd,stdout=output,stderr=subprocess.STDOUT,stdin=subprocess.PIPE,env=environment)
        except Exception as exc:
            job.close();output.close();activity.finish('failed',output=str(exc));self.uncertain=True
            raise UncertainCoding('Command launch outcome uncertain; no retry.') from exc
        self.sessions[key]={'process':process,'job':job,'output':output,'path':output_path,'activity':activity,
                            'deadline':time.monotonic()+min(180,max(1,float(timeout_seconds))),'offset':0,'tail':''}
        return self.poll(key,yield_time_ms=yield_time_ms)

    def poll(self, session_id, chars='', yield_time_ms=1000, max_output_tokens=3000):
        if session_id not in self.sessions: raise ValueError('Unknown or completed session; only this worker owned sessions may be polled.')
        row=self.sessions[session_id];p=row['process'];until=time.monotonic()+min(5,max(0,float(yield_time_ms)/1000))
        # Interactive input can cause side effects; input is explicitly finite and never repeated.
        if chars:
            if not isinstance(chars,str) or len(chars)>1000: raise ValueError('Input is limited to 1000 characters.')
            try:p.stdin.write(chars.encode());p.stdin.flush()
            except OSError as exc:
                self.close();self.uncertain=True
                raise UncertainCoding('Input delivery uncertain; command stopped without replay.') from exc
        while p.poll() is None:
            if self.cancelled() or time.monotonic()>=row['deadline']:
                self.uncertain=True;self._finish(session_id,'stopped')
                raise UncertainCoding('Command stopped or timed out; partial state retained, command not replayed.')
            if time.monotonic()>=until: break
            time.sleep(.05)
        size=row['path'].stat().st_size
        with row['path'].open('rb') as output:
            output.seek(max(row['offset'],size-min(24000,max(100,4*int(max_output_tokens)))))
            text=output.read().decode('utf-8',errors='replace')
        row['offset']=size
        row['tail']=(row['tail']+text)[-24000:]
        result={'session_id':session_id,'output':text,'exit_code':p.poll(),'running':p.poll() is None}
        if not result['running']:self._finish(session_id,'completed' if p.returncode==0 else 'failed',row['tail'])
        elif text:
            row['activity'].row['output']=row['tail'];emit(self.report,self.run,row['activity'].row)
        return result

    def _finish(self, key, state, text=''):
        row=self.sessions.pop(key);p=row['process'];row['job'].close()
        if p.poll() is None:
            p.kill();p.wait(timeout=5)
        row['activity'].finish(state,output=text,exit_code=p.poll())
        if p.stdin:p.stdin.close()
        row['output'].close()

    def close(self):
        for key in list(self.sessions): self._finish(key,'stopped')
