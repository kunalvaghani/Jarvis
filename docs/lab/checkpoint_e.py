"""Immutable local Phase E source/evidence checkpoint, no credentials or databases."""
import hashlib,json,zipfile,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PUBLIC=ROOT/'docs/lab/evidence'
receipt=json.loads((PUBLIC/'e-full-final.json').read_text())
if receipt['source_sha256_before']!=receipt['source_sha256_after'] or receipt['new_failure_ids']:
    raise ValueError('source-stable comparison without new failures required')
if runpy.run_path(str(ROOT/'docs/lab/run_checks.py'))['source_fingerprint']()!=receipt['source_sha256_after']:
    raise ValueError('current source differs from terminal regression')
audit=json.loads((PUBLIC/'e-current-audit.json').read_text())
if hashlib.sha256((ROOT/'app/benchmarks/live/discovery_lab.py').read_bytes()).hexdigest()!=audit['harness_sha256']:
    raise ValueError('benchmark source changed since the current audit')
paths=[ROOT/name for name in ('app/jarvis/discovery/acceptance.py','app/benchmarks/live/discovery_lab.py',
    'app/tests/test_discovery_acceptance.py','app/config/runtime_manifest.json','docs/lab/E_ACCEPTANCE.md',
    'docs/lab/reproduce_e.py','docs/lab/run_e_exports.py','docs/lab/prepare_e_exports.py','docs/lab/finalize_e.py',
    'docs/lab/archive_e_code.py','docs/lab/checkpoint_e.py')]
paths+=sorted(p for p in PUBLIC.glob('e-*') if p.suffix in ('.json','.cir','.txt') and p.name!='e-checkpoint.json')
entries=[]
for path in paths:
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT):raise ValueError('unsafe checkpoint path')
    entries.append({'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
target=ROOT/'app/.jarvis-runtime/lab-validation/e-source-evidence-checkpoint-2026-11-04.zip'
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
    for item in entries:archive.writestr(item['path'],(ROOT/item['path']).read_bytes())
with zipfile.ZipFile(target) as archive:
    if archive.testzip() is not None:raise ValueError('checkpoint integrity failure')
    for item in entries:
        if hashlib.sha256(archive.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('checkpoint bytes differ')
result={'date_local':'2026-11-04 Asia/Calcutta','kind':'local Phase E source/evidence checkpoint, not a full repository backup or Git release',
        'private_archive':target.relative_to(ROOT).as_posix(),'archive_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'expanded_source_sha256':receipt['source_sha256_after'],'entries':entries,
        'excludes':'credentials, personal memory, recordings, runtime databases, native binaries, unrelated working-tree files',
        'full_phase_e_acceptance':False,'commit_push_tag':False}
with (PUBLIC/'e-checkpoint.json').open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2)
print(json.dumps({'checkpoint_files':len(entries),'archive_sha256':result['archive_sha256'],'full_acceptance':False}))
