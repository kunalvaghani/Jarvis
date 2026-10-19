"""Keep dated repository overviews consistent with actual Prompt 35 evidence."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
packet = 'artifacts/jarvis-audit/modules/35-security/' + OUT.name
cases = list(ET.parse(OUT / 'final-regression.xml').getroot().iter('testcase'))
assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
final_pass = sum(c.find('skipped') is None for c in cases)

def block(path, text):
    text = text.replace('534', str(final_pass))
    content = path.read_text(encoding='utf-8')
    wrapped = '<!-- prompt35-security -->\n' + text + '\n<!-- /prompt35-security -->\n\n'
    if '<!-- prompt35-security -->' in content:
        content = re.sub(r'<!-- prompt35-security -->.*?<!-- /prompt35-security -->\s*', lambda m: wrapped, content, flags=re.S)
    else:
        anchor = '<!-- prompt34-repair -->'
        content = content.replace(anchor, wrapped + anchor, 1)
    path.write_text(content, encoding='utf-8')

block(APP / 'README.md', f'''**2026-10-20 — Prompt 35 local security repairs completed; release NOT READY.** Independent final relevant regression: **534 passed / 0 failed / 4 skipped**, plus **two separate evaluator/held-out tamper checks passed**. All use synthetic/owned fixtures; no real cloud requests, messages, desktop recording, package installation or model inference. The skipped OpenViking guard needs its isolated runtime path, native symlink creation needs Windows privilege, and live DPI/UAC checks remain unexecuted. A native junction containment probe separately passed with zero outside files.

Cloud examples now have bounded nested literal validation before serialization, constraints text has a size limit, and known confidential/proprietary markers stay local. The final tool entry point rejects malformed/deep/oversized JSON before provider construction; a finite 1,500-call malformed batch created zero providers. Tool reports redact colon/JSON credential assignments. Learned ability failures retain fixed diagnostic categories while withholding untrusted exception text/traceback source. AZR proposals with known private/credential text are quarantined before execution/dataset admission. Skill validation requires same-call/same-tool host outcome evidence; a tool's own success claim cannot replace failed or missing readback. Generated trust/admin/authorization declarations are refused. No dependency versions or configuration changed.

**Remaining gates:** caller-declared cloud provenance is not independent proof of generic semantics; uniform verifier authority, post-approval reparse races and all-sink/live trust coverage remain incomplete. Isolated launcher readiness is `repair_required`; nothing was installed to clear it. [Evidence and limits]({packet}/verdict.md) · [Threat model]({packet}/threat-model.md) · [24 case dispositions]({packet}/tests.jsonl) · [Cumulative Claude handoff](docs/CLAUDE_HANDOFF.md). Prompt 34 and earlier blockers remain in the same handoff.''')

block(APP.parent / 'README.md', f'''**2026-10-20 — Prompt 35 security repairs verified locally; release NOT READY.** **534 relevant tests passed, four skipped, no failures**, plus two separate evaluator tamper checks passed. Repairs cover cloud payload bounds, credential/error privacy, sensitive training proposals, skill privilege declarations and readback precedence. Semantic provenance and broader live trust gates remain open. [Application details](app/README.md) · [Independent evidence](app/{packet}/verdict.md) · [Cumulative Claude handoff](app/docs/CLAUDE_HANDOFF.md).''')

path = APP / 'docs/CRASH_RECOVERY.md'
content = path.read_text(encoding='utf-8')
addition = '''
## Security diagnostic boundary — 2026-10-20

Learned ability failure reports withhold untrusted exception messages and traceback source. Fixed permission/output-contract guidance and builtin error categories remain available for local repair, so repair can continue without storing arbitrary exception secrets. Tool report redaction now covers colon/JSON credential assignments and complete authorization schemes. Uncertain external writes still cannot be replayed.

The [Prompt 35 verification](../artifacts/jarvis-audit/modules/35-security/2026-10-20-completion-a9b4ce1/verdict.md) records 534 relevant passes/four skips and explicit remaining privacy/verification gates. This is fixture evidence, not a full live recovery or all-log privacy certificate. Keep unresolved work in the [Claude handoff](CLAUDE_HANDOFF.md).
'''
heading, rest = content.split('\n', 1)
addition = addition.replace('534', str(final_pass))
if '## Security diagnostic boundary — 2026-10-20' not in content:
    path.write_text(heading + '\n' + addition + rest, encoding='utf-8')
else:
    content = re.sub(r'(## Security diagnostic boundary — 2026-10-20.*?)(?=\n## |\Z)',
                     lambda m: addition.strip() + '\n', content, count=1, flags=re.S)
    path.write_text(content, encoding='utf-8')
print('Updated both README overviews and recovery diagnostic guidance.')
