"""Update dated overview without rewriting historical evidence."""
from pathlib import Path

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
packet = 'artifacts/jarvis-audit/modules/34-dependencies/' + OUT.name

def replace_block(path, body):
    text = path.read_text(encoding='utf-8')
    start = text.index('<!-- prompt34-repair -->')
    end = text.index('<!-- /prompt34-repair -->', start) + len('<!-- /prompt34-repair -->')
    path.write_text(text[:start] + '<!-- prompt34-repair -->\n' + body + '\n<!-- /prompt34-repair -->' + text[end:], encoding='utf-8')

replace_block(APP / 'README.md', f'''**2026-10-20 — Prompt 34 safe local repairs completed; full release NOT READY.** Independent final relevant regression: **227 passed / 0 failed / 1 skipped**, after additional authorization fixes on `codex-review` at `a9b4ce1` plus the recorded local patch. The original four unapproved install/download boundary tests pass unchanged. All ten installed environments pass dependency checks; brain/F5/training native imports pass. These checks do not certify clean offline installation, model inference or live voice/GPU acceptance. The earlier Claude-reported 3,511-pass suite is historical and separate from this selected independent run.

Startup and model recovery report missing dependencies/assets as `repair_required`; imports or missing model tags do not authorize installation/download. Explicit dependency repair uses a single-use grant naming the environment, hash-locked requirements, approved local wheelhouse and byte budget. Local hardening now rejects trailing pip options, unsafe grant IDs, invalid expiry and non-boolean network permission, and prevents concurrent consumption of one grant. No dependency versions changed. No packages, browser artifacts or models were installed/downloaded.

**Remaining gates:** approved model transport still pulls a mutable tag after checking a digest; staged venv relocation and immutable execution artifacts need validation. Actual offline rebuild/rollback, advisory reachability/remediation, WSL/native-engine paths and physical training/voice preemption remain incomplete. Bundled Chromium was absent; isolated launcher readiness is `repair_required`, with missing local env/assets and unavailable Docker/Ollama endpoints. Preserve working environments; do not run setup merely to clear this audit. [Current evidence]({packet}/verdict.md) · [Case dispositions]({packet}/tests.jsonl) · [Source patch]({packet}/source.patch) · [Cumulative Claude handoff](docs/CLAUDE_HANDOFF.md). The handoff now carries unresolved work across numbered prompts.''')

replace_block(APP.parent / 'README.md', f'''**2026-10-20 — Prompt 34 safe local repairs completed; release NOT READY.** Additional repair-authorization and concurrent-grant fixes pass **227 relevant tests, with one live-CUDA skip and no failures**. Ten installed environments pass dependency checks. Clean installation/rollback, immutable model transport and live hardware acceptance remain incomplete. [Application details](app/README.md) · [Independent evidence](app/{packet}/verdict.md) · [Cumulative Claude handoff](app/docs/CLAUDE_HANDOFF.md). Earlier Claude-reported full-suite results remain historical.''')

recovery = APP / 'docs/CRASH_RECOVERY.md'
text = recovery.read_text(encoding='utf-8')
heading, rest = text.split('\n', 1)
addition = '''
## Dependency recovery boundary — 2026-10-20

Missing imports, environments and model assets report `repair_required`; startup/recovery do not silently install packages or pull models. Explicit repair authorization is single-use and bounded by identity, expiry, artifacts and resources. Invalid/trailing pip options, unsafe IDs and non-boolean network permission are refused; concurrent grant consumers are serialized by a native OS file lock. Persistent lock files carry no ownership after process close/crash.

Approved model transport still needs immutable revision/byte-budget enforcement, and staged venv promotion needs executable relocation validation. Do not treat import-only staging checks as proven rollback or permission to run setup. See the [Claude handoff](CLAUDE_HANDOFF.md) and [independent verification](../artifacts/jarvis-audit/modules/34-dependencies/2026-10-20-completion-a9b4ce1/verdict.md): 227 relevant passes / one live CUDA skip, no real install/download. Full release remains blocked.
'''
recovery.write_text(heading + '\n' + addition + rest, encoding='utf-8')
print('Updated both READMEs and recovery guidance.')
