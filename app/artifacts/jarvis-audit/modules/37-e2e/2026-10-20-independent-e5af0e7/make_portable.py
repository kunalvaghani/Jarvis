"""Install only the new independent regression in the two owned test trees."""
from pathlib import Path

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
source = (OUT / 'test_ui_restart_journey.py').read_text(encoding='utf-8')
source = source.replace("APP = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')",
                        'APP = Path(__file__).resolve().parents[1]')
source = source.replace("'source_sha': 'e5af0e700517bac5fb48dcebc8f6cc9c9df9a369'",
    "'source_sha': subprocess.check_output(['git','rev-parse','HEAD'],cwd=APP,text=True).strip()")
source = source.replace("        (Path(__file__).parent / 'ui-restart-journal.json').write_text(json.dumps(record, indent=2), encoding='utf-8')",
    "        evidence = os.environ.get('JARVIS_E2E_EVIDENCE_DIR')\n"
    "        if evidence:\n"
    "            destination = Path(evidence)\n"
    "            destination.mkdir(parents=True, exist_ok=True)\n"
    "            (destination / 'ui-restart-journal.json').write_text(json.dumps(record, indent=2), encoding='utf-8')")
for path in [APP / 'tests/test_prompt37_ui_restart.py',
             Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app/tests/test_prompt37_ui_restart.py')]:
    assert not path.exists()
    path.write_text(source, encoding='utf-8')
print('Portable regression added; pinned checkout has a test-only overlay.')
