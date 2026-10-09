"""Optional trained CPU coding inference in an isolated, bounded subprocess."""
import json
from pathlib import Path
import subprocess


def generate(base, checkpoint, request):
    base = Path(base).resolve()
    checkpoint = (base / checkpoint).resolve()
    if not checkpoint.is_relative_to(base/'artifacts') or not (checkpoint/'adapter_model.safetensors').is_file():
        raise ValueError('Trained coder checkpoint must be an existing local training artifact')
    interpreter = base/'.venv-training/Scripts/python.exe'
    if not interpreter.is_file():
        raise ValueError('Trained coder environment is missing')
    context = {key:request.get(key) for key in ('goal','path','reason','current','references',
              'repository_instructions','selected_skills','previous','validation_error','pc_context')}
    completed = subprocess.run([str(interpreter), '-m', 'scripts.training.qwen_jarvis_coder',
                     '--checkpoint',str(checkpoint), '--request-stdin'],
                     input=json.dumps(context, ensure_ascii=False), text=True, encoding='utf-8',
                     capture_output=True, cwd=base, timeout=130,
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0), check=False)
    if completed.returncode:
        raise ValueError('Trained coder inference failed: '+completed.stderr[-1000:])
    result = json.loads(completed.stdout)
    if not isinstance(result.get('content'),str) or not result['content'].strip():
        raise ValueError('Trained coder returned empty source')
    return result
