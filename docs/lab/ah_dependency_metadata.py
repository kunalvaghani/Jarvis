"""Bounded official metadata only. Never downloads packages or installs/runs them."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def read(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Jarvis-readonly-compatibility-audit'}),timeout=30) as response:
        raw=response.read(12_000_001)
    if len(raw)>12_000_000:raise ValueError('official metadata cap exceeded')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def main():
    result={'date_local':'2026-11-04 Asia/Calcutta','scope':'public official metadata only, no package download/install/execution','sources':{}}
    url='https://api.anaconda.org/package/projectchrono/pychrono';data,digest=read(url)
    files=[r for r in data['files'] if r.get('attrs',{}).get('subdir')=='win-64' and 'release' in r.get('labels',[])]
    files.sort(key=lambda r:r.get('upload_time',''),reverse=True)
    result['sources']['pychrono']={'url':url,'metadata_sha256':digest,'latest_version':data.get('latest_version'),'license':data.get('license'),
        'recent_release_windows_files':[{k:r.get(k) for k in ('basename','version','size','sha256','md5','download_url','labels','attrs')} for r in files[:6]]}
    url='https://api.github.com/repos/mamba-org/micromamba-releases/releases/latest';data,digest=read(url)
    result['sources']['micromamba']={'url':url,'metadata_sha256':digest,'tag':data['tag_name'],
        'windows_assets':[{k:r.get(k) for k in ('name','size','digest','browser_download_url')} for r in data['assets'] if 'win-64' in r['name']]}
    for name in ('mujoco','pybamm','matplotlib','trimesh'):
        url='https://pypi.org/pypi/'+name+'/json';data,digest=read(url)
        result['sources'][name]={'url':url,'metadata_sha256':digest,'version':data['info']['version'],
            'requires_python':data['info'].get('requires_python'),'license':data['info'].get('license_expression') or data['info'].get('license'),
            'requires_dist':data['info'].get('requires_dist'),
            'windows_or_pure_wheels':[{k:r.get(k) for k in ('filename','size','digests','url')} for r in data['urls']
                if r['filename'].endswith('.whl') and ('win_amd64' in r['filename'] or 'none-any' in r['filename'])]}
    path=ROOT/'docs/lab/evidence/ah-official-dependency-metadata.json'
    with path.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
