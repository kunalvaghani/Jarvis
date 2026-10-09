"""Bounded CPU inference with fresh-path validation; no action execution."""
import json
from pathlib import Path
import subprocess
from .pc_context import validate_resolution


def resolve(base,checkpoint,goal,entries,kind=None):
    base=Path(base).resolve();checkpoint=(base/checkpoint).resolve()
    if not checkpoint.is_relative_to(base/'artifacts') or not (checkpoint/'adapter_model.safetensors').is_file():
        raise ValueError('PC adapter must be an existing local artifact')
    result=subprocess.run([str(base/'.venv-training/Scripts/python.exe'),'-m', 'scripts.training.qwen_pc_resolver','--checkpoint',str(checkpoint)],
                          input=json.dumps({'goal':goal,'entries':entries,'kind':kind}),text=True,encoding='utf-8',
                          capture_output=True,cwd=base,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('PC resolver inference failed: '+result.stderr[-500:])
    data=json.loads(result.stdout)
    if not isinstance(data,dict) or not isinstance(data.get('model_used'),str):
        raise ValueError('PC resolver returned an invalid envelope')
    proposal=validate_resolution(data.get('proposal'),goal,entries,kind)
    return {'resolution':proposal,'model_used':data['model_used'],'validated_against_live_paths':True}
