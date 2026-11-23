"""Preserve a code-only checkpoint after the final source-stable regression."""
import hashlib
import json
import runpy
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'
PUBLIC=ROOT/'docs/lab/evidence'


def main():
    result=json.loads((PUBLIC/'scenario-a-final-regression.json').read_text(encoding='utf-8'))
    fingerprint=runpy.run_path(str(ROOT/'docs/lab/run_checks.py'))['source_fingerprint']
    source=fingerprint()
    if not result['regression_gate_passed'] or result['source_sha256_after']!=source:
        raise ValueError('passing current-source terminal regression required')
    paths=[*sorted((APP/'jarvis').rglob('*.py')),*sorted((APP/'tests').rglob('*.py')),
        *sorted((APP/'requirements').glob('*.txt')),*sorted((APP/'requirements').glob('*.json')),
        *sorted((APP/'jarvis/discovery/neurons').glob('*.json')),
        *sorted((APP/'jarvis/skills/discovery').rglob('SKILL.md')),
        *sorted((APP/'benchmarks/live').rglob('*.py')),
        APP/'config/runtime_manifest.json',APP/'README.md',ROOT/'README.md',
        ROOT/'docs/lab/SCENARIO_A_WORKFLOW.md',ROOT/'app/docs/CLAUDE_HANDOFF.md',
        *sorted((ROOT/'docs/lab').glob('*.py'))]
    home=APP/'.jarvis-runtime/lab-validation/checkpoints'/('scenario-a-'+source[:12])
    home.mkdir(parents=True,exist_ok=False)
    entries=[]
    target=home/'source.zip'
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):raise ValueError('unsafe checkpoint source')
            raw=path.read_bytes();relative=path.relative_to(ROOT).as_posix()
            entries.append({'path':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
            archive.writestr(relative,raw)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:raise ValueError('checkpoint CRC failure')
        for item in entries:
            if hashlib.sha256(archive.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('checkpoint content differs')
    if fingerprint()!=source:raise ValueError('source changed during checkpoint')
    (home/'files.json').write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    summary={'date':'2026-11-06','scope':'Code-only mixed-worktree checkpoint; not a release, full backup or clean Git commit',
        'source_sha256':source,'file_count':len(entries),'uncompressed_bytes':sum(p['bytes'] for p in entries),
        'private_archive':target.relative_to(ROOT).as_posix(),'archive_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'excluded':'credentials/config.json contents, personal memory, recordings, runtime databases, downloaded tools/models/binaries',
        'restore_policy':'Do not restore blindly over mixed user work. Compare individual files; no automatic rollback or deletion.'}
    with (PUBLIC/'scenario-a-checkpoint.json').open('x',encoding='utf-8') as stream:json.dump(summary,stream,indent=2)
    print(json.dumps(summary))


if __name__=='__main__':main()
