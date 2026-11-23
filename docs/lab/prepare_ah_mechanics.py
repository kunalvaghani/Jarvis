"""Approved isolated mechanics preparation. No main-env changes or generated code.

Stage plan: new stdlib venv + wheel-only pip dry-run report.
Stage wheels: bounded official downloads, SHA/path/link checks and license copies.
Stage install: only after the retained licenses have been reviewed, offline/hash-locked.
"""
import argparse,hashlib,json,os,subprocess,sys,urllib.request,urllib.parse,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app'
ENV=APP/'.venv-discovery-mechanics';HOME=APP/'.jarvis-runtime/lab-validation/ah-mechanics-setup'
TOP=('mujoco==3.17.0','trimesh==5.2.0','matplotlib==3.11.2')
CAP=250_000_000

def write(path,data):
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2)

def run(args,timeout=180):
    env={**os.environ,'PIP_DISABLE_PIP_VERSION_CHECK':'1','PYTHONDONTWRITEBYTECODE':'1',
         'TMP':str(HOME/'tmp'),'TEMP':str(HOME/'tmp'),'PIP_CACHE_DIR':str(HOME/'cache')}
    p=subprocess.run([str(a) for a in args],env=env,timeout=timeout,capture_output=True)
    if p.returncode:
        print(p.stderr.decode(errors='replace')[-5000:]);raise RuntimeError('owned setup command failed')
    return p.stdout.decode(errors='replace')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('plan','wheels','install'));p.add_argument('--licenses-reviewed',action='store_true');args=p.parse_args()
    HOME.mkdir(parents=True,exist_ok=True);(HOME/'tmp').mkdir(exist_ok=True)
    if args.stage=='plan':
        authorization={'scope':'user-approved-ah-mechanics-2026-11-04','max_download_bytes':CAP,'max_owned_disk_bytes':2_000_000_000,
            'top_level':list(TOP),'max_cpu_invocations':50,'host_generated_code':False,'main_env_changes':False}
        if ENV.exists():
            if not (HOME/'resolve.json').exists() or json.loads((HOME/'authorization.json').read_text(encoding='utf-8'))!=authorization:
                raise ValueError('new environment already exists without a matching resolved preparation; inspect, never overwrite')
        else:
            write(HOME/'authorization.json',authorization)
            run([sys.executable,'-B','-m','venv',ENV])
            run([ENV/'Scripts/python.exe','-B','-m','pip','--isolated','--disable-pip-version-check','--no-cache-dir','install',
                '--dry-run','--ignore-installed','--only-binary=:all:','--index-url','https://pypi.org/simple','--report',HOME/'resolve.json',*TOP])
        resolved=json.loads((HOME/'resolve.json').read_text(encoding='utf-8'));pins=[];total=0
        for row in resolved['install']:
            info=row['download_info'];url=info['url'];parts=urllib.parse.urlsplit(url)
            if parts.scheme!='https' or parts.hostname!='files.pythonhosted.org' or not parts.path.endswith('.whl'):raise ValueError('official binary wheel required')
            digest=info['archive_info']['hashes']['sha256']
            request=urllib.request.Request(url,method='HEAD')
            with urllib.request.urlopen(request,timeout=30) as response:size=int(response.headers['Content-Length'])
            total+=size
            pins.append({'name':row['metadata']['name'],'version':row['metadata']['version'],'url':url,'sha256':digest,'bytes':size,
                         'filename':PurePosixPath(parts.path).name,'license_expression':row['metadata'].get('license_expression'),
                         'license_metadata':str(row['metadata'].get('license',''))[:300]})
        if total>CAP-30_000_000:raise ValueError('wheel closure plus metadata safety allowance exceeds download cap')
        write(HOME/'lock.json',{'wheel_bytes':total,'metadata_allowance_bytes':30_000_000,'pins':pins})
        print(json.dumps({'stage':'planned','packages':len(pins),'wheel_bytes':total,'pins':[(r['name'],r['version']) for r in pins]}));return
    lock=json.loads((HOME/'lock.json').read_text(encoding='utf-8'));wheels=HOME/'wheels';wheels.mkdir(exist_ok=True)
    if args.stage=='wheels':
        licenses=HOME/'licenses';licenses.mkdir(exist_ok=True);total=0;summary=[]
        for row in lock['pins']:
            path=wheels/row['filename']
            if path.exists():
                if path.stat().st_size!=row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('staged wheel differs; retain it, do not overwrite')
            else:
                with urllib.request.urlopen(row['url'],timeout=30) as response,path.open('xb') as out:
                    size=0
                    while chunk:=response.read(65536):
                        size+=len(chunk)
                        if size>row['bytes'] or total+size>CAP-30_000_000:raise ValueError('approved download cap reached')
                        out.write(chunk)
            total+=path.stat().st_size
            if path.stat().st_size!=row['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('official wheel hash/length mismatch')
            texts=[]
            with zipfile.ZipFile(path) as archive:
                if sum(i.file_size for i in archive.infolist())>1_000_000_000:raise ValueError('wheel expansion too large')
                for item in archive.infolist():
                    name=PurePosixPath(item.filename)
                    if name.is_absolute() or '..' in name.parts or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('unsafe wheel member')
                    if any(s in name.name.casefold() for s in ('license','copying','notice')):
                        if item.file_size>1_000_000:raise ValueError('license text unexpectedly large')
                        texts.append(item.filename+'\n'+archive.read(item).decode('utf-8','replace'))
            if not texts:raise ValueError('no retained license text for '+row['name'])
            target=licenses/(row['name']+'-'+row['version']+'.txt')
            if not target.exists():
                with target.open('x',encoding='utf-8') as out:out.write('\n\n'.join(texts))
            summary.append({'name':row['name'],'version':row['version'],'license_file':str(target.relative_to(APP)),
                            'license_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'texts':len(texts)})
        write(HOME/'license-index.json',summary);print(json.dumps({'stage':'staged-not-installed','wheel_bytes':total,'packages':summary}));return
    if not args.licenses_reviewed:raise ValueError('retained package licenses must be reviewed before installation')
    if not (HOME/'license-index.json').exists():raise ValueError('license review inputs missing')
    requirements='\n'.join(row['name']+'=='+row['version']+' --hash=sha256:'+row['sha256'] for row in lock['pins'])+'\n'
    with (HOME/'locked-requirements.txt').open('x',encoding='utf-8') as out:out.write(requirements)
    run([ENV/'Scripts/python.exe','-B','-m','pip','--isolated','--disable-pip-version-check','install','--no-index','--find-links',wheels,
         '--only-binary=:all:','--require-hashes','-r',HOME/'locked-requirements.txt'])
    footprint=sum(p.stat().st_size for root in (ENV,HOME) for p in root.rglob('*') if p.is_file())
    if footprint>2_000_000_000:raise ValueError('owned footprint exceeds approved cap; retain files and inspect')
    write(HOME/'installed.json',{'scope':'user-approved-ah-mechanics-2026-11-04','env':str(ENV.relative_to(APP)),
        'lock_sha256':hashlib.sha256((HOME/'lock.json').read_bytes()).hexdigest(),'footprint_bytes':footprint,'main_env_changed':False})
    print(json.dumps({'stage':'installed','footprint_bytes':footprint,'main_env_changed':False}))

if __name__=='__main__':main()
