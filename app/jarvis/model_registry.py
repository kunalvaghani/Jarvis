"""Registry of locally trained checkpoints; every entry starts and stays *experimental* until approved.

Approval requires a ``qualified_experimental`` decision from the sealed model gate, a passing export
compatibility check (merged model reproduces the adapter's greedy outputs), unchanged adapter bytes,
and an explicit approval card. Even then the registry only records the approval: it never edits
``config.json``, never replaces a configured endpoint and never registers a model with Ollama.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ModelRegistry:
    def __init__(self, base):
        self.path = Path(base) / '.jarvis-runtime' / 'models' / 'registry.json'

    def entries(self):
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []

    def _save(self, rows):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(rows, indent=1), encoding='utf-8')
        temporary.replace(self.path)

    def register(self, adapter, base_sha256, dataset_sha256, gate_report, export_check=None):
        adapter = Path(adapter)
        row = {'id': 'model_' + uuid.uuid4().hex[:10], 'adapter': str(adapter),
               'adapter_sha256': _sha(adapter / 'adapter_model.safetensors'), 'base_sha256': base_sha256,
               'dataset_manifest_sha256': dataset_sha256, 'gate_decision': gate_report.get('decision'),
               'gate_seal': gate_report.get('seal'), 'export_check': export_check, 'status': 'experimental',
               'registered_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        rows = self.entries()
        rows.append(row)
        self._save(rows)
        return row

    def approve(self, identifier, approve, cancelled=lambda: False):
        rows = self.entries()
        row = next((r for r in rows if r['id'] == identifier), None)
        if row is None:
            raise ValueError('Unknown model entry.')
        if row['gate_decision'] != 'qualified_experimental':
            raise ValueError('Only a checkpoint that qualified on the sealed held-out gate can be approved.')
        export = row.get('export_check') or {}
        if export.get('exact_match_rate', 0) < 0.95 or not export.get('merged_reloads_with_transformers'):
            raise ValueError('Export compatibility has not been demonstrated.')
        if _sha(Path(row['adapter']) / 'adapter_model.safetensors') != row['adapter_sha256']:
            raise ValueError('Adapter bytes changed since evaluation.')
        approve('model_promotion', 'Mark trained checkpoint ' + identifier + ' as approved for future use? '
                'No configuration, endpoint or Ollama model is changed by this approval.', cancelled)
        row['status'] = 'approved'
        row['approved_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self._save(rows)
        return row
