"""Run Jarvis's reply drafter without the full Jarvis window (the same service Jarvis starts on launch).

    python scripts/run_mail_replies.py          # one pass (the 30-day backfill the first time), then exit
    python scripts/run_mail_replies.py --watch  # keep checking new mail every interval_seconds

Prints counts only, never mail content. Drafts are never sent.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'benchmarks' / 'live'))


def main() -> int:
    from runner import build  # Jarvis's headless Actions (benchmarks/live)
    from jarvis.mail_replies import MailReplies
    config = json.loads((APP / 'config' / 'config.json').read_text(encoding='utf-8'))
    actions, _events, _approvals = build('deny', None, True, False, (), True)
    replies = MailReplies(actions, config.get('mail_replies') or {})
    if '--watch' in sys.argv:
        replies.start()
        replies.thread.join()  # type: ignore[union-attr]
        return 0
    summary = replies.run_once()
    print(json.dumps(summary))
    for row in replies.drafted()[-50:]:
        print('drafted reply ->', row.get('to', ''), '|', str(row.get('subject', ''))[:80])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
