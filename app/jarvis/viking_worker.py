"""One-shot OpenViking client worker, run with .venv-openviking/Scripts/python.exe.

OpenViking (volcengine/OpenViking, AGPL-3.0) is installed unmodified in its own
environment and runs as a separate loopback server process. Jarvis never imports
it: this worker uses the published openviking_sdk HTTP client and exchanges one
bounded JSON request/reply over stdin/stdout.
"""
import json
import sys

LIMIT = 1_000_000
OPERATIONS = {'add', 'find', 'tree', 'read', 'abstract', 'overview', 'remove', 'health'}


def client(request):
    import openviking_sdk as ov
    connection = ov.SyncHTTPClient(url=request['url'], api_key=request['key'], account='jarvis', user='jarvis',
                                   timeout=request.get('timeout', 600))
    connection.initialize()
    return connection


def run(request):
    operation = request['operation']
    if operation not in OPERATIONS:
        raise ValueError('Unsupported OpenViking operation.')
    connection = client(request)
    if operation == 'health':
        return {'tree_root': len(connection.ls('viking://resources', simple=True))}
    if operation == 'add':
        from openviking_sdk import AddResourceOptions
        options = AddResourceOptions(include=request.get('include'), exclude=request.get('exclude'),
                                     ignore_dirs=request.get('ignore_dirs'), preserve_structure=True,
                                     processing_mode=request.get('processing_mode', 'vectors_only'),
                                     # One stored Markdown body per source file keeps verified links to the vault.
                                     args={'parse_mode': 'no_split'})
        result = connection.add_resource(request['path'], to=request['to'], wait=True,
                                         timeout=request.get('timeout', 600), options=options)
        meta = result.get('meta', {}) if isinstance(result, dict) else {}
        return {'status': result.get('status'), 'root_uri': result.get('root_uri'),
                'processed': [row.get('path') for row in meta.get('processed_files', [])][:5000],
                'failed': meta.get('failed_files', [])[:200], 'errors': result.get('errors', [])[:50],
                'queue': result.get('queue_status')}
    if operation == 'find':
        result = connection.find(query=request['query'], target_uri=request.get('target', ''),
                                 limit=request.get('limit', 5))
        rows = []
        for kind in ('resources', 'memories', 'skills'):
            for row in result.get(kind, []) or []:
                rows.append({'type': kind, 'uri': row.get('uri'), 'level': row.get('level'),
                             'score': row.get('score'), 'abstract': str(row.get('abstract', ''))[:1200]})
        return {'results': rows}
    if operation == 'tree':
        return {'nodes': [{k: node.get(k) for k in ('uri', 'rel_path', 'isDir', 'size', 'name')}
                          for node in connection.tree(request['uri'], level_limit=request.get('depth', 6),
                                                      node_limit=request.get('limit', 5000))]}
    if operation == 'read':
        return {'content': connection.read(request['uri'])[:request.get('max_chars', 200000)]}
    if operation == 'abstract':
        return {'content': connection.abstract(request['uri'])[:4000]}
    if operation == 'overview':
        return {'content': connection.overview(request['uri'])[:12000]}
    if operation == 'remove':
        connection.rm(request['uri'], recursive=True, wait=True, timeout=request.get('timeout', 300))
        return {'removed': request['uri']}


def main():
    try:
        raw = sys.stdin.buffer.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('OpenViking request exceeds 1 MB.')
        text = json.dumps({'ok': True, 'value': run(json.loads(raw))}, default=str, ensure_ascii=False)
    except Exception as error:  # Reported as a typed failure; the host decides what to do.
        text = json.dumps({'ok': False, 'error_type': type(error).__name__, 'error': str(error)[:500]})
    sys.stdout.buffer.write(text.encode('utf-8'))


if __name__ == '__main__':
    main()
