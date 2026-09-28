"""Audit saved held-out outputs without executing generated JavaScript."""
import argparse
import json
from pathlib import Path
import re
import sqlite3

from jarvis.polyglot_training_data import TASKS
from train_polyglot_qwen import SCHEMA, save


def audit(run):
    heldout = [row for row in TASKS if row['split'] == 'heldout']
    groups = {}
    stages = ['baseline', *(path.name for path in sorted(run.glob('round-*-evaluation')) if path.is_dir())]
    for stage in stages:
        records = []
        for row in heldout:
            source = (run / stage / row['id'] / 'response.txt').read_text(encoding='utf-8').strip()
            record = {'id': row['id'], 'language': row['language']}
            if row['language'] == 'javascript':
                # This is only an interface/static review. No generated JS runs.
                record['interface_valid'] = bool(re.search(
                    r'module\.exports\s*=\s*\{[^}]*\bsolve\b[^}]*\}', source)) and '```' not in source
                record['external_dependency'] = bool(re.search(r"require\(['\"](?!node:|fs['\"]|path['\"])[^'\"]+['\"]\)", source))
                record['functional_pass'] = None
            else:
                record['interface_valid'] = bool(re.fullmatch(r'\s*SELECT\b[^;]*;?\s*', source, re.I | re.S))
                record['functional_pass'] = False
                if record['interface_valid']:
                    connection = sqlite3.connect(':memory:')
                    try:
                        connection.executescript(SCHEMA)
                        connection.execute('PRAGMA query_only = ON')
                        ticks = [0]
                        def limit():
                            ticks[0] += 1
                            return ticks[0] > 10000
                        connection.set_progress_handler(limit, 100)
                        actual = [list(item) for item in connection.execute(source)]
                        record['functional_pass'] = actual == row['expected']
                    except sqlite3.Error:
                        pass
                    finally:
                        connection.close()
            records.append(record)
        groups[stage] = records
    result = {'run': str(run), 'scope': 'four held-out tasks on one fixed fixture',
              'generated_javascript_executed': False, 'groups': groups}
    save(run / 'contract-audit.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.run.resolve()), indent=2))


if __name__ == '__main__':
    main()
