"""Approved exact isolated setup; never resolves packages or runs package scripts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'
PLAN=APP/'.jarvis-runtime/discovery/tools/micromamba-2.10.0-0'
HOME=APP/'.jarvis-runtime/discovery/tools/chrono-10.0.0'
PREFIX=APP/'.venv-discovery-chrono'
sys.path.insert(0,str(APP))


def save(name,data):
    with (HOME/name).open('x',encoding='utf-8') as f:json.dump(data,f,indent=2)


def disk_bytes():
    return sum(p.stat().st_size for root in (HOME,PREFIX) if root.exists()
               for p in root.rglob('*') if p.is_file())


def run(argv,timeout):
    from jarvis.harness_process import OwnedJob,hidden_spawn
    from jarvis.repo_acquisition import environment
    env=environment();env['USERPROFILE']=str(PLAN/'empty-profile')
    job=OwnedJob();process=None
    try:
        with tempfile.TemporaryFile() as output:
            process=hidden_spawn(job,subprocess.Popen)(argv,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=output)
            deadline=time.monotonic()+timeout
            next_disk=0
            while process.poll() is None:
                now=time.monotonic()
                if now>deadline or os.fstat(output.fileno()).st_size>16_000_000:
                    raise ValueError('owned setup deadline/output cap reached; no replay')
                if now>next_disk:
                    if disk_bytes()>14_000_000_000:raise ValueError('owned 14 GB disk cap reached')
                    next_disk=now+2
                time.sleep(.2)
            output.seek(0);body=output.read(16_000_001)
            if process.returncode:raise ValueError('setup failed: '+body.decode(errors='replace')[-1600:])
            return body
    finally:
        job.close()
        if process is not None:process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['download','extract','inspect','install'])
    a=parser.parse_args()
    HOME.mkdir(parents=True,exist_ok=True)
    raw=(PLAN/'dry-run.json').read_bytes();plan=json.loads(raw)
    if not plan['success'] or not plan['dry_run']:raise ValueError('successful dry-run required')
    rows=plan['actions']['FETCH']
    if len(rows)!=72 or sum(r['size'] for r in rows)!=1_913_155_814:raise ValueError('approved package set changed')
    binary=PLAN/'micromamba.exe'
    if hashlib.sha256(binary.read_bytes()).hexdigest()!='f8b4284bd4eb1134122eaf93b3ea6c7be567e596de5829e1a6f478e34e41974a':raise ValueError('planner binary changed')
    help_text=(PLAN/'create-help.txt').read_text()
    if '--skip-run-link-scripts' not in help_text or '--no-pyc' not in help_text:raise ValueError('script-free linking switches unavailable')
    downloads=HOME/'archives';downloads.mkdir(exist_ok=True)
    if a.stage=='download':
        save('download-started.json',{'approval':'2026-11-05 isolated setup and tests','plan_sha256':hashlib.sha256(raw).hexdigest(),
             'max_download_bytes':2_100_000_000,'max_owned_disk_bytes':14_000_000_000})
        def fetch(row):
            url=row['url'];parts=urllib.parse.urlsplit(url)
            if parts.scheme!='https' or parts.hostname!='conda.anaconda.org' or not parts.path.startswith(('/conda-forge/','/projectchrono/label/release/')):
                raise ValueError('unapproved archive source')
            name=row['fn']
            if Path(name).name!=name or any(c in name for c in '/\\:'):raise ValueError('invalid archive name')
            target=downloads/name;pending=downloads/(name+'.pending')
            digest=hashlib.sha256();count=0
            with pending.open('xb') as out:
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Jarvis-approved-isolated-Chrono-setup'}),timeout=60) as response:
                    while True:
                        block=response.read(1024*1024)
                        if not block:break
                        count+=len(block)
                        if count>row['size']:raise ValueError('archive exceeds approved size')
                        out.write(block);digest.update(block)
                out.flush();os.fsync(out.fileno())
            if count!=row['size'] or digest.hexdigest()!=row['sha256']:raise ValueError('archive hash/size mismatch')
            pending.rename(target)
            print(json.dumps({'downloaded':row['name'],'bytes':count}),flush=True)
            return {'name':name,'sha256':digest.hexdigest(),'bytes':count}
        with ThreadPoolExecutor(max_workers=3) as pool:done=list(pool.map(fetch,rows))
        save('download-verified.json',{'archives':done,'bytes':sum(r['bytes'] for r in done)})
        return
    proof=json.loads((HOME/'download-verified.json').read_text())
    if len(proof['archives'])!=72:raise ValueError('complete download proof required')
    for row in rows:
        target=downloads/row['fn']
        h=hashlib.sha256()
        with target.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        if target.stat().st_size!=row['size'] or h.hexdigest()!=row['sha256']:raise ValueError('verified archive changed')
    lock=HOME/'explicit-local.txt'
    expected='@EXPLICIT\n'+'\n'.join((downloads/r['fn']).as_uri()+'#'+r['md5'] for r in rows)+'\n'
    if lock.exists():
        if lock.read_text()!=expected:raise ValueError('explicit archive set changed')
    else:lock.write_text(expected,encoding='utf-8')
    argv=[str(binary),'--no-rc','--root-prefix',str(HOME/'cache'),'create','--offline','--yes','--json',
          '--skip-run-link-scripts','--no-pyc','--safety-checks','enabled','--extra-safety-checks',
          '--prefix',str(PREFIX),'--file',str(lock)]
    if a.stage=='extract':
        save('extract-started.json',{'argv':argv+['--download-only']})
        result=run(argv+['--download-only'],600)
        with (HOME/'extract-result.json').open('xb') as f:f.write(result)
        print('Archives extracted only; no linking/package scripts.')
    elif a.stage=='inspect':
        if not (HOME/'extract-result.json').exists():raise ValueError('extract first')
        packages=[]
        for row in rows:
            name=row['fn'].removesuffix('.conda').removesuffix('.tar.bz2')
            matches=[p.parent.parent for p in (HOME/'cache/pkgs').rglob('info/index.json')
                     if p.parent.parent.name==name]
            if len(matches)!=1:raise ValueError('ambiguous or absent extracted package: '+name)
            folder=matches[0]
            index=json.loads((folder/'info/index.json').read_text())
            if (index['name'],index['version'],index['build'])!=(row['name'],row['version'],row['build']):raise ValueError('extracted package identity mismatch')
            paths=json.loads((folder/'info/paths.json').read_text()).get('paths',[])
            if any(p.is_symlink() for p in folder.rglob('*')):raise ValueError('linked extracted package refused')
            scripts=[]
            for item in paths:
                relative=item['_path'];p=Path(relative)
                if p.is_absolute() or '..' in p.parts or ':' in relative or '\\' in relative:raise ValueError('unsafe archive path')
                low=relative.casefold()
                if any(k in low for k in ('pre-link.','post-link.','pre-unlink.','post-unlink.')):scripts.append(relative)
            if scripts:raise ValueError('package link scripts present; installation blocked: '+row['name'])
            licenses=[p for p in (folder/'info').rglob('*') if p.is_file() and any(k in p.name.casefold() for k in ('license','copying','notice'))]
            license_origin='archive info files'
            if not licenses and row['name']=='pychrono' and row['version']=='10.0.0':
                supplemental=HOME/'licenses/Chrono-10.0.0-LICENSE.txt'
                provenance=json.loads((HOME/'licenses/Chrono-10.0.0-source.json').read_text())
                if (provenance['url']!='https://raw.githubusercontent.com/projectchrono/chrono/10.0.0/LICENSE'
                        or hashlib.sha256(supplemental.read_bytes()).hexdigest()!=provenance['sha256']
                        or provenance['sha256']!='5f625eb4c9e0ddf86db9d1ed9b6adb5b30296ea81919282b2f38c977136bf079'):
                    raise ValueError('official supplemental license changed')
                licenses=[supplemental]
                license_origin='official upstream 10.0.0 license; binary archive omits BSD text'
            if not licenses:raise ValueError('license text missing: '+row['name'])
            packages.append({'name':row['name'],'license':row['license'],'license_origin':license_origin,
                             'license_files':[str(p.relative_to(HOME)) for p in licenses],
                             'license_sha256':[hashlib.sha256(p.read_bytes()).hexdigest() for p in licenses],'paths':len(paths),'link_scripts':[]})
        save('inspection.json',{'packages':packages,'passed':True,'owned_disk_bytes':disk_bytes(),'package_scripts_executed':False})
        print(json.dumps({'inspected':len(packages),'passed':True,'owned_disk_bytes':disk_bytes()}))
    else:
        inspection=json.loads((HOME/'inspection.json').read_text())
        if not inspection['passed'] or len(inspection['packages'])!=72:raise ValueError('inspection required')
        if PREFIX.exists():
            # --download-only creates an empty history marker, but links no package.
            entries={p.relative_to(PREFIX).as_posix() for p in PREFIX.rglob('*')}
            if (entries!={'conda-meta','conda-meta/history'}
                    or (PREFIX/'conda-meta/history').read_bytes()!=b''):
                raise ValueError('nonempty existing environment; no replay')
        save('install-started.json',{'argv':argv,'scripts_enabled':False})
        result=run(argv,600)
        with (HOME/'install-result.json').open('xb') as f:f.write(result)
        print(json.dumps({'prefix':str(PREFIX),'owned_disk_bytes':disk_bytes(),'package_scripts_executed':False}))


if __name__=='__main__':main()
