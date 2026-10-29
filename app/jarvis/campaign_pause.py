"""Narrow, persistent execution barrier for the explicitly paused repair campaign.

Uses existing queue/group pause state; this module only protects entry points
and frozen campaign paths. Ordinary intake, services and model routes stay live.
"""
import json
import hashlib
from pathlib import Path
import zipfile

BASE=Path(__file__).resolve().parents[1]


class CampaignPaused(RuntimeError):
    pass


def marker(base=None):
    return Path(base or BASE)/'.jarvis-runtime/autonomous-repair/pause.json'


def state(base=None):
    path=marker(base)
    if not path.exists():return None
    if path.stat().st_size>262144:raise CampaignPaused('Campaign pause metadata exceeds its limit; inspect the saved checkpoint.')
    try:value=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:raise CampaignPaused('Campaign pause metadata is unreadable; inspect the saved checkpoint.') from error
    if (not isinstance(value,dict) or value.get('schema_version')!=1 or value.get('status')!='PAUSED_BY_USER'
            or not isinstance(value.get('protected_roots'),list)
            or any(not isinstance(p,str) or not Path(p).is_absolute() for p in value['protected_roots'])):
        raise CampaignPaused('Unsupported campaign pause metadata; explicit compatibility review required.')
    return value


def assert_allowed(*,project=None,run=None,logical_task=None,whole_campaign=False,base=None):
    value=state(base)
    if value is None:return
    protected=[Path(p).resolve() for p in value['protected_roots']]
    paths=[Path(p).resolve() for p in (project,run) if p is not None]
    blocked=(whole_campaign or logical_task in value.get('logical_task_ids',[])
        or any(path.is_relative_to(root) for path in paths for root in protected))
    if blocked:
        raise CampaignPaused('Autonomous repair campaign is PAUSED_BY_USER. No inference, task dispatch or source write permitted. '
            'Read docs/AUTONOMOUS_REPAIR_RESUME.md; resume requires an explicit user request and compatibility verification.')


def queue_paused(store):
    value=store.setting('autonomous_repair_pause')
    return isinstance(value,dict) and value.get('status')=='PAUSED_BY_USER'


def fingerprint(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def verify_checkpoint(directory,*,compare_current=False,base=None):
    """Read back archives and flag upgrades for review; never restores any state."""
    from .workload_state import latest_checkpoint
    directory=Path(directory).resolve(strict=True);saved=latest_checkpoint(directory)
    if saved.get('status')!='PAUSED_BY_USER' or saved.get('pause_checkpoint_schema')!=1:
        raise ValueError('Not a completed supported pause checkpoint.')
    if saved.get('checkpoint_recovery_required'):raise ValueError('A newer checkpoint is unreadable; explicit recovery review required.')
    for name,expected in saved.get('auxiliary_files',{}).items():
        path=(directory/name).resolve(strict=True)
        if not path.is_relative_to(directory) or fingerprint(path)!=expected:raise ValueError('Checkpoint auxiliary file fingerprint mismatch.')
    checked=0
    for row in saved['archives']:
        archive=(directory/row['archive']).resolve(strict=True);manifest=(directory/row['manifest']).resolve(strict=True)
        if not archive.is_relative_to(directory) or not manifest.is_relative_to(directory):raise ValueError('Checkpoint path escapes its directory.')
        if fingerprint(archive)!=row['sha256'] or fingerprint(manifest)!=row['manifest_sha256']:
            raise ValueError('Checkpoint archive or manifest fingerprint mismatch.')
        value=json.loads(manifest.read_text(encoding='utf-8'));files=value.get('files',value.get('source_files'))
        if not isinstance(files,list) or len(files)!=row['entries']:raise ValueError('Checkpoint file inventory mismatch.')
        with zipfile.ZipFile(archive) as bundle:
            if set(bundle.namelist())!={item['path'] for item in files}:raise ValueError('Archive entries differ from the manifest.')
            for item in files:
                name=item['path']
                if name.startswith(('/','\\')) or '..' in Path(name).parts:raise ValueError('Unsafe checkpoint archive path.')
                digest=hashlib.sha256()
                with bundle.open(name) as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
                if digest.hexdigest()!=item['sha256']:raise ValueError('Archived file fingerprint mismatch: '+name)
                checked+=1
    differences=[]
    if compare_current:
        for name,expected in saved['critical_files'].items():
            path=Path(base or BASE)/name
            if not path.is_file() or fingerprint(path)!=expected:differences.append({'kind':'interface_or_configuration_review','path':name})
        for row in saved['frozen_files']:
            path=Path(row['path'])
            if not path.is_file() or fingerprint(path)!=row['sha256']:differences.append({'kind':'frozen_artifact_changed','path':str(path)})
    return {'status':'REVIEW_REQUIRED' if differences else 'PASS','checkpoint':str(directory),
        'archive_integrity':'PASS','archived_files_checked':checked,'current_architecture_compared':compare_current,
        'differences':differences,'restored_files':0,'inference_requests':0,
        'resume_authorized':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Read-only paused-campaign status and recovery verification; never resumes work.')
    parser.add_argument('action',nargs='?',choices=['status','verify'],default='status')
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--compare-current',action='store_true')
    args=parser.parse_args()
    if args.action=='verify':
        if not args.checkpoint:parser.error('verify requires --checkpoint')
        result=verify_checkpoint(args.checkpoint,compare_current=args.compare_current)
        print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASS' else 3)
    value=state()
    print(json.dumps({'status':value['status'] if value else 'NO_CAMPAIGN_PAUSE',
        'checkpoint':value.get('checkpoint') if value else None,
        'normal_features_disabled':False,'protected_roots':len(value['protected_roots']) if value else 0},indent=2))
