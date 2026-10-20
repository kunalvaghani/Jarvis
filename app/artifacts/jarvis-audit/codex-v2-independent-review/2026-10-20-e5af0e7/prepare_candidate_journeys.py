from pathlib import Path
out=Path(__file__).resolve().parent
body=(out/'run_journeys.py').read_text(encoding='utf-8')
body=body.split('# Fixed source/fixture comparison:',1)[0]
body=body.replace('Jarvis-e2e-e5af0e7/app','Jarvis-v2-mutants-e5af0e7/app')
body=body.replace("OUT / 'workflow-journals.jsonl'","OUT / 'candidate-workflow-journals.jsonl'")
body+="\nprint('Three final candidate owned/simulated journals written.')\n"
(out/'run_candidate_journeys.py').write_text(body,encoding='utf-8')
