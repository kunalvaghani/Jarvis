"""Re-seal the verifiers after a reviewed change: python -m jarvis.learning.verifiers --seal"""
import json
import sys

from . import seal

if sys.argv[1:] != ['--seal']:
    sys.exit(__doc__)
print(json.dumps(seal(), indent=1))
