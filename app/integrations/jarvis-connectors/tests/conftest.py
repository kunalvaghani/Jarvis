import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]          # jarvis-connectors/
APP = next(p for p in ROOT.parents if (p / 'main.py').is_file())  # Jarvis app/ (for bridge tests)
for path in (ROOT, APP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load_connector(folder, attribute):
    """Import connectors/<folder>/server.py and return the connector class."""
    source = ROOT / 'connectors' / folder / 'server.py'
    name = 'connector_' + folder.replace('/', '_')
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # lets tests patch module globals (e.g. urlopen)
    spec.loader.exec_module(module)
    return getattr(module, attribute)
