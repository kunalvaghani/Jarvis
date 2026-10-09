"""Read-only real-name checks; optional single Explorer launch and fresh verification."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from jarvis.catalog import Catalog
from jarvis.commands import parse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2]
    config = json.loads((base / 'config/config.json').read_text(encoding='utf-8'))
    catalog = Catalog(config, base)
    expected = Path('D:/Ollama').resolve(strict=True)
    phrases = ['open Ollama folder in D drive', 'open Ollama in D drive',
        'open Olamind D drive', 'open Olamide D drive', 'open Olama in D drive']
    rows = []
    for phrase in phrases:
        command = parse(phrase)
        started = time.perf_counter()
        path = catalog.resolve(command.value, 'folder', prefer_usage=True)
        rows.append({'request': phrase, 'seconds': round(time.perf_counter()-started, 6),
            'correct': Path(path) == expected, 'route': command.kind})
        if Path(path) != expected:
            raise ValueError('Unexpected folder match; no folder was opened.')
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'lookup': rows,
        'scope': 'Actual folder resolution; excludes speech recognition/output. Live opens once only when requested.'}
    if args.live:
        from jarvis.actions import Actions
        import pythoncom
        import win32com.client
        actions = Actions(config, base, lambda *_: None)
        try:
            started = time.perf_counter()
            actions.execute(parse(phrases[0]))
            pythoncom.CoInitialize()
            try:
                verified = False
                while time.perf_counter()-started < 8:
                    for window in win32com.client.Dispatch('Shell.Application').Windows():
                        try:
                            if Path(window.Document.Folder.Self.Path) == expected:
                                verified = True
                                break
                        except Exception:
                            continue
                    if verified:
                        break
                    time.sleep(.15)
                report['explorer'] = {'verified': verified, 'seconds': round(time.perf_counter()-started, 3),
                    'evidence': 'Fresh Shell.Application Explorer folder path equals requested D:/Ollama.' if verified else 'No matching Explorer folder was observed within eight seconds.'}
            finally:
                pythoncom.CoUninitialize()
        finally:
            actions.close()
    destination = base / 'artifacts/reports/folder-lookup-check.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
