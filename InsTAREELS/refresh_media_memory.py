"""Refresh owned tool reference notes while preserving the existing PC inventory."""
from datetime import datetime, timezone
import json
from pathlib import Path
from jarvis.memory_index import DIRECT_OPERATIONS, _atomic_text, tool_entries, write_tools_note


def main():
    base = Path(__file__).resolve().parent
    config = json.loads((base / 'config.json').read_text(encoding='utf-8'))
    if not config.get('memory', {}).get('enabled'):
        raise ValueError('Obsidian memory is disabled.')
    vault = Path(config['memory']['vault'])
    if not vault.is_absolute():
        vault = base / vault
    index = vault / 'Jarvis Index.json'
    data = json.loads(index.read_text(encoding='utf-8'))
    data['tools'] = tool_entries()
    data['operations'] = dict(DIRECT_OPERATIONS)
    updated = datetime.now(timezone.utc).isoformat()
    data['tools_updated_at_utc'] = updated
    note = dict(data, generated_at_utc=updated)
    write_tools_note(vault, note)
    _atomic_text(index, json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'tools_refreshed': len(data['tools']), 'media_control_available': any(row['name'] == 'media_control' for row in data['tools']), 'operations_refreshed': len(data['operations'])}))


if __name__ == '__main__':
    main()
