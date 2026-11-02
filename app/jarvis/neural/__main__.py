"""Brain command line (local only).

    python -m jarvis.neural status                 neurons, synapses, graph version, learning summary
    python -m jarvis.neural rebuild                re-read every source; journal a new graph version if it changed
    python -m jarvis.neural route "<request>"      what the brain would fire for a request, and why (no action)
    python -m jarvis.neural export [folder]        Obsidian projection (default .jarvis-runtime/brain/obsidian)
    python -m jarvis.neural viewer [port]          live neuron view on 127.0.0.1
    python -m jarvis.neural replay                 shadow agreement report
    python -m jarvis.neural consolidate            propose neurons from repeated verified chains
    python -m jarvis.neural proposals              pending neuron proposals
    python -m jarvis.neural approve <node_id>      activate a proposed neuron (the user's decision)
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import List

APP = Path(__file__).resolve().parents[2]


def main(argv: List[str]) -> int:
    if not argv:
        print(__doc__)
        return 0
    config = json.loads((APP / 'config' / 'config.json').read_text(encoding='utf-8'))
    from .service import BrainService
    service = BrainService(config)
    command, rest = argv[0], argv[1:]
    out: object
    if command == 'status':
        from .learning import summary
        out = {'registry': service.registry.summary(), 'graph': service.graph.stats(),
               'learning': summary(service.journal), 'versions': service.journal.versions()[-5:]}
    elif command == 'rebuild':
        out = {'version': service.rebuild(), 'graph': service.graph.stats()}
    elif command == 'route':
        out = service.route(' '.join(rest)).as_dict()
    elif command == 'export':
        from .projection import export_obsidian
        out = export_obsidian(service.journal, Path(rest[0]) if rest else APP / '.jarvis-runtime' / 'brain' / 'obsidian')
    elif command == 'viewer':
        from .viewer import serve
        _, address = serve(service.journal.path, int(rest[0]) if rest else 0)
        print(f'Jarvis brain view: {address}  (Ctrl+C to stop)', flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
    elif command == 'replay':
        from .learning import replay
        out = replay(service.journal)
    elif command == 'consolidate':
        from .learning import consolidate
        out = consolidate(service.journal, service.registry)
    elif command == 'proposals':
        out = [n.node_id for n in service.registry.nodes.values() if n.status == 'proposed']
    elif command == 'approve' and rest:
        out = service.registry.approve(rest[0]).model_dump(mode='json')
        service.rebuild()
    else:
        print(__doc__)
        return 2
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
