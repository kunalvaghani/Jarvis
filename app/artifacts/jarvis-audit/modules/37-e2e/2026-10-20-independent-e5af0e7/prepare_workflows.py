from pathlib import Path

OUT = Path(__file__).resolve().parent
prior = OUT.parent / '2026-10-20-followup-a9b4ce1/run_journeys.py'
source = prior.read_text(encoding='utf-8')
source = source.replace("APP = next(p for p in OUT.parents if (p / 'main.py').is_file())",
    "APP = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')")
source = source.replace('P37-FOLLOWUP', 'P37-E5AF')
(OUT / 'run_workflows.py').write_text(source, encoding='utf-8')
