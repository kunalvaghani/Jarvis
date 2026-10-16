"""Reproduce precommit RAM/disk divergence on saved old code and verify fix."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.memory_curator import MemoryCurator


def main():
    spec=importlib.util.spec_from_file_location('jarvis._curator_fault_before',BASE/'.jarvis-runtime/jarvis-audit/module16-pre/jarvis__memory_curator.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    result={'date':'2026-10-16 IST','scope':'Injected Path.replace failure on isolated canonical temporary fact JSON; no external effects/replay.'}
    with tempfile.TemporaryDirectory() as root:
        for name,cls in [('before',old.MemoryCurator),('after',MemoryCurator)]:
            c=cls(Path(root)/name);c.add('Kunal prefers tea')
            with patch.object(Path,'replace',side_effect=OSError('synthetic disconnected store')) as replace:
                try:c.add('Kunal prefers coffee')
                except OSError:pass
                else:raise AssertionError('Expected fixture write refusal')
            disk=json.loads(c.facts_path.read_text(encoding='utf-8'))['facts']
            result[name]={'ram_matches_disk':c.facts==disk,'commit_attempts':replace.call_count}
            assert replace.call_count==1
    assert not result['before']['ram_matches_disk'] and result['after']['ram_matches_disk']
    result['passed']=True
    (BASE/'artifacts/jarvis-audit/modules/16-memory/durability-reproduction.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
