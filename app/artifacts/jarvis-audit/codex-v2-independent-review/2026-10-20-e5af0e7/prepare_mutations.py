from pathlib import Path

out = Path(__file__).resolve().parent
old = out.parent / '2026-10-20-a9b4ce1/mutate.py'
body = old.read_text(encoding='utf-8')
body = body.replace("APP = next(p for p in OUT.parents if (p / 'main.py').is_file())",
                    "APP = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')")
body = body.replace('Jarvis-codex-v2-baseline', 'Jarvis-v2-mutants-e5af0e7')
body = body.replace("assert TARGET.name == 'app'", "assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=TARGET).decode().strip() == 'e5af0e700517bac5fb48dcebc8f6cc9c9df9a369'\nassert TARGET.name == 'app'")
body = body.replace("assert target.read_bytes() == original", "assert target.read_bytes() == original\n        restored = check(name + '-restored', node)\n        rows[-1]['restored_control'] = restored\n        assert restored['returncode'] == 0")
(out/'mutate.py').write_text(body, encoding='utf-8')
