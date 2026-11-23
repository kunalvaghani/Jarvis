"""Copy only hash-verified scientific outputs; never rerun a solver or overwrite evidence."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=['A1','A2'],required=True)
    parser.add_argument('--attempt',type=int,required=True)
    args=parser.parse_args()
    audit=json.loads((ROOT/f'docs/lab/evidence/scenario-{args.case.lower()}-attempt-{args.attempt}-audit.json').read_text())
    if audit['status']!='PASS_CONDITIONAL_SURROGATE':raise ValueError('independent audit required')
    output=ROOT/f'docs/lab/evidence/scenario-a-corrected-2026-11-06/{args.case}'
    output.mkdir(parents=True,exist_ok=False)
    project=f".jarvis-runtime/discovery/scenario-projects/{audit['run_id']}/"
    manifest={}
    for relative,expected in audit['artifact_hashes'].items():
        if relative.startswith(project):name=relative[len(project):]
        elif relative.startswith('.jarvis-runtime/discovery/vehicle-runs/'):
            name='native/'+relative.split('/vehicle-runs/',1)[1]
        else:continue  # Do not redistribute copyrighted FIA PDFs/index captures.
        if '..' in Path(name).parts or Path(name).is_absolute():raise ValueError('unsafe artifact path')
        raw=(APP/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('actual artifact hash differs')
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        manifest[name]=expected
    (output/'bundle_manifest.json').write_text(json.dumps({'scope':'Actual conditional surrogate outputs; no physical validation or exact team CAD',
        'case':args.case,'original_run_id':audit['run_id'],'audit':f'../../scenario-{args.case.lower()}-attempt-{args.attempt}-audit.json',
        'files':manifest},indent=2)+'\n')
    print(json.dumps({'case':args.case,'exported_files':len(manifest)}))


if __name__=='__main__':main()
