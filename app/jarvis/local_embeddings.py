"""Local text embeddings through Ollama (nomic-embed-text, Apache-2.0). No cloud calls.

Returns None when the local model or server is unavailable so callers fall back to
lexical retrieval and report that they did. Inputs are bounded; nothing is logged.
"""
import json
import math
import threading
import urllib.error
import urllib.request

MODEL = 'nomic-embed-text'
ENDPOINT = 'http://127.0.0.1:11434/api/embed'
_LOCK = threading.Lock()
_STATE = {'available': None}


def embed(texts, kind='document', timeout=30):
    """kind: 'document' or 'query' (nomic task prefixes). Returns list of vectors or None."""
    if not isinstance(texts, list) or not texts or len(texts) > 64:
        raise ValueError('Embed 1-64 texts at a time.')
    prefix = 'search_query: ' if kind == 'query' else 'search_document: '
    # Small vector reads must not occupy the 4 GB speech/planner GPU outside
    # the priority scheduler. Keep the same local weights and lexical fallback.
    body = json.dumps({'model': MODEL, 'input': [prefix + str(t)[:4000] for t in texts],
                       'keep_alive': '10m', 'options': {'num_gpu': 0}}).encode()
    request = urllib.request.Request(ENDPOINT, data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            vectors = json.loads(response.read(8_000_000)).get('embeddings')
    except (OSError, ValueError, urllib.error.URLError):
        with _LOCK:
            _STATE['available'] = False
        return None
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        return None
    with _LOCK:
        _STATE['available'] = True
    return [normalize(v) for v in vectors]


def normalize(vector):
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


def status():
    return {'model': MODEL, 'available': _STATE['available']}
