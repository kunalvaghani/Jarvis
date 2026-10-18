"""Phase 4 measurements: lesson retrieval quality/latency and exploration success with vs without lessons.

Retrieval set: 12 authored lessons and 12 paraphrased queries with one labelled correct
lesson each (authored oracle, not user data). Compares the token-overlap scoring Jarvis
memories used before Phase 4 against ReasoningBank retrieval with local
nomic-embed-text embeddings. Exploration: the real isolated headless-browser fixture.
"""
import argparse
from datetime import datetime, timezone
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

LESSONS = [
    ('xlsx', 'Edit spreadsheet cells through the workbook API and read the values back.'),
    ('docx', 'Change document paragraphs with the document adapter and confirm the text.'),
    ('pdf', 'Merge or split pages into a new file rather than editing the original.'),
    ('blender', 'Export glTF scenes as binary .glb files from a disposable scene.'),
    ('browser', 'Fill required form fields before pressing the submit control.'),
    ('spotify', 'Use the media session controls to pause or skip tracks.'),
    ('gmail', 'Create a draft first and wait for approval before sending mail.'),
    ('vscode', 'Open source files at a line with the editor command line.'),
    ('weather', 'Query the registered weather provider instead of scraping pages.'),
    ('git', 'Inspect repository status before committing any change.'),
    ('docker', 'Run untrusted code only in the network-less container sandbox.'),
    ('obsidian', 'Search the vault index and open the linked source note.'),
]
QUERIES = [
    ('update numbers in my excel sheet', 'xlsx'), ('rewrite a section of the word report', 'docx'),
    ('combine two pdfs into one', 'pdf'), ('save my 3d model for a game engine', 'blender'),
    ('the form complains a field is required', 'browser'), ('skip this song', 'spotify'),
    ('reply to an email for me', 'gmail'), ('jump to line 40 in main.py', 'vscode'),
    ('will it rain tomorrow', 'weather'), ('commit my code changes', 'git'),
    ('run this script safely', 'docker'), ('find my notes about the project', 'obsidian'),
]


def tokens(text):
    import re
    return {w for w in re.findall(r'[a-z][a-z0-9]+', text.casefold()) if len(w) > 2}


def summary(values):
    values = sorted(values)
    return {'n': len(values), 'p50_ms': round(statistics.median(values), 2), 'p95_ms': round(values[int((len(values) - 1) * .95)], 2)}


def retrieval():
    from jarvis.reasoning_bank import ReasoningBank
    from jarvis.local_embeddings import embed
    result = {}
    # Baseline: token-overlap ranking (the approach of experience/skill memory before Phase 4).
    hits = sum(max(LESSONS, key=lambda l: len(tokens(q) & tokens(l[0] + ' ' + l[1])))[0] == label for q, label in QUERIES)
    result['token_overlap_precision_at_1'] = round(hits / len(QUERIES), 3)
    if embed(['probe']) is None:
        result['embedding'] = 'BLOCKED: local embedding model unavailable'
        return result
    with tempfile.TemporaryDirectory() as folder:
        bank = ReasoningBank(Path(folder))
        ids = {}
        for label, content in LESSONS:
            ids[bank._add({'kind': 'strategy', 'title': label + ' lesson', 'description': 'Authored benchmark lesson.',
                           'content': content, 'conditions': {}}, {'task_id': label}, 'benchmark')] = label
        correct, latencies = 0, []
        for query, label in QUERIES:
            started = time.perf_counter()
            found = bank.retrieve(query, k=1)['lessons']
            latencies.append((time.perf_counter() - started) * 1000)
            correct += bool(found) and ids.get(found[0]['id']) == label
        result['reasoning_bank_embedding_precision_at_1'] = round(correct / len(QUERIES), 3)
        result['retrieve_latency'] = summary(latencies)
    return result


def exploration():
    from jarvis.exploration import Explorer, IsolatedBrowserEnv
    from jarvis.reasoning_bank import ReasoningBank
    handler = functools.partial(type('Quiet', (SimpleHTTPRequestHandler,), {'log_message': lambda *a: None}),
                                directory=str(BASE / 'tests' / 'fixtures'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    rows = {}
    try:
        for label in ('with_lessons', 'without_lessons'):
            with tempfile.TemporaryDirectory() as folder:
                bank = ReasoningBank(Path(folder)) if label == 'with_lessons' else None
                explorer = Explorer(Path(folder), bank=bank, approved=('fixture-web',))
                attempts, latencies = 0, []
                for _ in range(4):
                    started = time.perf_counter()
                    run = explorer.episode('fixture-web', IsolatedBrowserEnv(origin, '/exploration_app.html'),
                                           hint_values={'Format': 'csv'})
                    latencies.append((time.perf_counter() - started) * 1000)
                    if run.get('goal_id') == 'Export':
                        attempts += 1
                        if run['status'] == 'completed':
                            break
                rows[label] = {'export_attempts_until_verified': attempts if run.get('status') == 'completed' else None,
                               'episode': summary(latencies)}
    finally:
        server.shutdown()
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    out = Path(parser.parse_args(argv).out)
    if out.exists():
        raise SystemExit('Refusing to overwrite preserved measurements: ' + str(out))
    result = {'schema_version': 1, 'measured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'scope': 'Authored retrieval oracle (12 lessons, 12 paraphrased queries) and the isolated loopback fixture app.',
              'retrieval': retrieval(), 'exploration': exploration()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
