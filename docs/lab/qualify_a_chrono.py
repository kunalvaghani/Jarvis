"""Reserve one of 50 approved fixed CPU calls, then qualify the actual owned worker."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'
HOME=APP/'.jarvis-runtime/discovery/tools/chrono-10.0.0'
PREFIX=APP/'.venv-discovery-chrono'
WORKER=APP/'jarvis/discovery/adapters/chrono_worker.py'
sys.path.insert(0,str(APP))


def main():
    if sys.argv[1:]!=['--run']:raise SystemExit('Explicit --run required')
    if not (HOME/'install-result.json').exists():raise ValueError('approved install receipt required')
    slots=HOME/'invocations';slots.mkdir(exist_ok=True)
    digest=hashlib.sha256(WORKER.read_bytes()+WORKER.with_name('chrono_vehicle_worker.py').read_bytes()).hexdigest()
    snapshot=HOME/'worker-sources'/digest;snapshot.mkdir(parents=True,exist_ok=True)
    for source in (WORKER,WORKER.with_name('chrono_vehicle_worker.py')):
        path=snapshot/source.name
        if path.exists():
            if path.read_bytes()!=source.read_bytes():raise ValueError('qualified worker snapshot changed')
        else:
            with path.open('xb') as f:f.write(source.read_bytes())
    for index in range(50):
        slot=slots/f'slot-{index:02}.json'
        try:
            with slot.open('x') as f:json.dump({'state':'consumed-before-dispatch','worker_sha256':digest,'operation':'canonical'},f)
            break
        except FileExistsError:continue
    else:raise PermissionError('50 Chrono calls exhausted; no automatic reset')
    from jarvis.repo_acquisition import command
    result={'slot':index,'worker_sha256':digest,'passed':False,'full_A_acceptance_passed':False}
    try:
        raw=command([str(PREFIX/'python.exe'),'-I','-B',str(WORKER)],timeout=120,
                    input_bytes=b'{"operation":"canonical"}',limit=2_000_000)
        with (HOME/f'canonical-{index:02}-raw-private.txt').open('xb') as f:f.write(raw)
        lines=[line for line in raw.decode(errors='replace').splitlines() if line.startswith('JARVIS_CHRONO_RESULT=')]
        if len(lines)!=1:raise ValueError('one exact worker result required')
        report=json.loads(lines[0].split('=',1)[1])
        if not report.get('passed'):raise ValueError('worker did not pass')
        result.update(passed=True,report=report)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)[:1200]
    with (HOME/f'canonical-{index:02}.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))


if __name__=='__main__':main()
