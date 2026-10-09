"""Owned, cancellable Node commands and preview. Never replays uncertain commands."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import build_opener, ProxyHandler
import uuid
from .agent_context import scoped
from .harness_process import OwnedJob, hidden_spawn

def executable(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(name + ' is missing. Install Node.js LTS and restart Jarvis.')
    return path

def binary(project, name):
    paths = {'tsc': 'node_modules/typescript/bin/tsc', 'vite': 'node_modules/vite/bin/vite.js',
             'next': 'node_modules/next/dist/bin/next', 'expo': 'node_modules/expo/bin/cli'}
    if name not in paths:
        raise ValueError('Unsupported development binary.')
    # npm package trees legitimately contain package links; the project root and
    # dependency root themselves must stay inside this exact project.
    dependency = scoped(project, 'node_modules')
    path = scoped(project, paths[name])
    if not path.is_file() or not path.resolve().is_relative_to(dependency.resolve()):
        raise ValueError('Install project-local ' + name + ' with approved development tooling first.')
    return [executable('node'), str(path)]

class DevelopmentTools:
    def __init__(self, base, report=lambda *a:None):
        self.base=Path(base).resolve()
        self.report=report
        self.lock=threading.RLock()
        self.preview=None
        self.command=None
        self.closed=False

    def run(self, project, argv, cancelled, seconds=180):
        project=Path(project).resolve(strict=True)
        if cancelled() or self.closed:
            raise ValueError('Development command cancelled before execution.')
        job=OwnedJob()
        with tempfile.TemporaryFile() as output:
            with self.lock:
                if self.closed or cancelled():
                    job.close()
                    raise ValueError('Development tooling closed.')
                if self.command is not None:
                    job.close()
                    raise ValueError('Another owned development command is still active.')
                try:
                    process=hidden_spawn(job,subprocess.Popen)(argv,cwd=project,stdin=subprocess.DEVNULL,
                        stdout=output,stderr=output,env={**os.environ,'CI':'1','NEXT_TELEMETRY_DISABLED':'1','EXPO_NO_TELEMETRY':'1'})
                except Exception:
                    job.close()
                    raise
                self.command=(process,job)
            try:
                deadline=time.monotonic()+seconds
                while process.poll() is None:
                    if self.closed or cancelled() or time.monotonic()>deadline:
                        raise ValueError('Command cancelled or timed out; inspect generated files before retrying. No command replayed.')
                    time.sleep(.05)
                output.seek(0,2)
                size=output.tell()
                output.seek(max(0,size-16000))
                result={'argv':list(map(str,argv)),'exit_code':process.returncode,
                        'output':output.read().decode('utf-8',errors='replace')}
                return result
            finally:
                job.close()
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)
                with self.lock:
                    if self.command and self.command[0] is process:
                        self.command=None

    def install(self, project, cancelled):
        npm=executable('npm.cmd' if os.name=='nt' else 'npm')
        # Explicit project approval is required by the caller. Package hooks are
        # disabled; Electron's binary download/packaging is a separate operation.
        manifest=json.loads(scoped(project,'package.json').read_text(encoding='utf-8'))
        import re
        for section in ('dependencies','devDependencies','optionalDependencies'):
            for name,version in manifest.get(section,{}).items():
                if not re.fullmatch(r'(?:@[a-z0-9._-]+/)?[a-z0-9._-]+',name) or not isinstance(version,str) or not re.fullmatch(r'[0-9xX*^~>=<|. +a-zA-Z-]{1,100}',version) or not re.search(r'[0-9]',version):
                    raise ValueError('Only reviewed npm registry version dependencies are supported: '+str(name))
        lock=scoped(project,'package-lock.json')
        locked=json.loads(lock.read_text(encoding='utf-8')).get('packages',{}).get('',{}) if lock.is_file() else {}
        compatible=bool(locked) and all(locked.get(k,{})==manifest.get(k,{}) for k in ('dependencies','devDependencies','optionalDependencies'))
        command='ci' if compatible else 'install'
        return self.run(project,[npm,command,'--ignore-scripts','--no-audit','--no-fund',
                                '--registry=https://registry.npmjs.org'],cancelled,300)

    def build(self, project, stack, cancelled):
        checks=[('typecheck',binary(project,'tsc')+['--noEmit'])]
        if stack in {'vite','electron'}:
            checks.append(('build',binary(project,'vite')+['build']))
        elif stack=='next':
            checks.append(('build',binary(project,'next')+['build']))
        elif stack=='expo':
            checks.append(('build',binary(project,'expo')+['export','--platform','web']))
        else:
            raise ValueError('Build adapter unavailable for this existing stack; no framework replaced.')
        rows=[]
        for phase,argv in checks:
            from .progress import status
            status(self.report,'Development '+phase,project)
            result=self.run(project,argv,cancelled,300)
            rows.append({'phase':phase,**result})
            if result['exit_code']:
                break
        return rows

    def start_preview(self, project, stack, cancelled):
        self.stop_preview()
        if self.closed or cancelled():
            raise ValueError('Preview cancelled.')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        if stack in {'vite','electron'}:
            argv=binary(project,'vite')+['preview','--host','127.0.0.1','--port',str(port),'--strictPort']
        elif stack=='next':
            argv=binary(project,'next')+['start','--hostname','127.0.0.1','--port',str(port)]
        elif stack=='expo':
            output=scoped(project,'dist')
            if not (output/'index.html').is_file():
                raise ValueError('Expo web export missing; inspect build output.')
            argv=[sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1','--directory',str(output)]
        else:
            raise ValueError('Preview adapter unavailable.')
        log=tempfile.TemporaryFile()
        job=OwnedJob()
        with self.lock:
            if self.closed or cancelled():
                job.close(); log.close()
                raise ValueError('Preview closed before launch.')
            try:
                process=hidden_spawn(job,subprocess.Popen)(argv,cwd=project,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                    env={**os.environ,'NEXT_TELEMETRY_DISABLED':'1'})
            except Exception:
                job.close(); log.close()
                raise
            self.preview={'process':process,'job':job,'log':log,'project':str(Path(project).resolve()),
                          'url':f'http://127.0.0.1:{port}','desired':True,'argv':argv,'started':time.monotonic()}
        until=time.monotonic()+30
        while time.monotonic()<until:
            if cancelled() or self.closed or process.poll() is not None:
                self.stop_preview()
                raise ValueError('Preview stopped or cancelled; it was not replayed.')
            if self.healthy():
                return self.preview['url']
            time.sleep(.1)
        self.stop_preview()
        raise ValueError('Owned preview failed its loopback health check.')

    def healthy(self):
        with self.lock:
            item=self.preview
            if not item or not item['desired'] or self.closed:
                return True
            if item['process'].poll() is not None:
                return False
            try:
                with build_opener(ProxyHandler({})).open(item['url'],timeout=.5) as response:
                    return response.status==200
            except OSError:
                return False

    def repair(self):
        # Running project code again may repeat server-side effects. Pause and
        # retain fresh evidence, then require explicit continuation instead.
        self.stop_preview()
        self.report('repair','Development preview stopped. Inspect the project and explicitly start its preview; no project code replayed.')
        from .recovery import record
        record(self.base,'Development preview stopped; no build, install or server execution replayed.')
        return True

    def inspect(self, project, url, tests, cancelled):
        from urllib.parse import urlsplit
        with self.lock:
            if not self.preview or self.preview['project']!=str(Path(project).resolve()) or url!=self.preview['url']:
                raise ValueError('Inspect only this Jarvis-owned project preview.')
        parsed=urlsplit(url)
        if parsed.hostname!='127.0.0.1' or parsed.scheme!='http':
            raise ValueError('Development inspection requires owned loopback preview.')
        directory=scoped(project,'.jarvis/development/run-'+uuid.uuid4().hex)
        directory.mkdir(parents=True)
        request=directory/'request.json'
        request.write_text(json.dumps({'project':str(Path(project).resolve()),'url':url,'tests':tests,'output':str(directory)}),encoding='utf-8')
        # Worker uses the app's interpreter and import path, not the project's.
        result=self.run(self.base,[sys.executable,'-m','jarvis.development_browser',str(request)],cancelled,120)
        evidence=directory/'browser.json'
        if result['exit_code'] or not evidence.is_file():
            raise ValueError('Browser inspection failed: '+result['output'][-1500:])
        return json.loads(evidence.read_text(encoding='utf-8'))

    def stop_preview(self):
        with self.lock:
            item,self.preview=self.preview,None
        if item:
            item['desired']=False
            item['job'].close()
            if item['process'].poll() is None:
                item['process'].terminate()
            item['process'].wait(timeout=10)
            item['log'].close()

    def close(self):
        with self.lock:
            self.closed=True
            item=self.command
            if item:
                item[1].close()
        self.stop_preview()
