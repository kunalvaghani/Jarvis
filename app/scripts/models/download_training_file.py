"""Resumable parallel HTTP range download for explicitly selected training files."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import threading
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('destination', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--workers', type=int, default=12)
    args = parser.parse_args()
    dest = args.destination.resolve()
    base = Path(__file__).resolve().parents[2] / 'models'
    if not dest.is_relative_to(base):
        parser.error('Training downloads must stay under models/')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(args.url, headers={'Range':'bytes=0-0'}, stream=True, timeout=30) as response:
        response.raise_for_status()
        if response.status_code != 206:
            raise ValueError('Server does not support resumable ranges')
        size = int(response.headers['Content-Range'].split('/')[-1])
        download_url = response.url
    chunk = 8*1024*1024
    count = (size+chunk-1)//chunk
    statefile = dest.with_suffix(dest.suffix+'.download.json')
    partial = dest.with_suffix(dest.suffix+'.partial')
    state = {'url':args.url,'size':size,'chunk':chunk,'complete':[]}
    if statefile.exists():
        state = json.loads(statefile.read_text())
        if state['url'] != args.url or state['size'] != size or state['chunk'] != chunk:
            raise ValueError('Download resume metadata mismatch')
        if not partial.exists():
            raise ValueError('Resume partial file missing')
    else:
        with partial.open('xb') as stream:
            stream.truncate(size)
        statefile.write_text(json.dumps(state))
    sessions = threading.local()
    def fetch(index):
        if not hasattr(sessions, 'client'):
            sessions.client = requests.Session()
        start = index*chunk
        end = min(size,start+chunk)-1
        for attempt in range(4):
            try:
                with sessions.client.get(download_url, headers={'Range':f'bytes={start}-{end}'}, stream=True, timeout=(20,40)) as response:
                    response.raise_for_status()
                    if response.status_code != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{size}':
                        raise ValueError('Unexpected HTTP range response')
                    data = response.content
                    if len(data) != end-start+1:
                        raise ValueError('Incomplete chunk')
                with partial.open('r+b') as stream:
                    stream.seek(start)
                    stream.write(data)
                    stream.flush()
                return index
            except (requests.RequestException, ValueError):
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(fetch,i) for i in range(count) if i not in state['complete']]
        for future in as_completed(futures):
            index = future.result()
            state['complete'].append(index)
            temp = statefile.with_suffix('.tmp')
            temp.write_text(json.dumps(state))
            temp.replace(statefile)
            print(json.dumps({'chunks':len(state['complete']), 'total_chunks':count,
                              'seconds':round(time.monotonic()-started,1)}), flush=True)
    digest = hashlib.sha256()
    with partial.open('rb') as stream:
        while data := stream.read(1024*1024):
            digest.update(data)
    if args.sha256 and digest.hexdigest() != args.sha256:
        raise ValueError('Downloaded checksum mismatch; partial preserved')
    if dest.exists():
        raise ValueError('Refusing to overwrite existing completed model/dependency file')
    partial.replace(dest)
    print(json.dumps({'completed':str(dest),'sha256':digest.hexdigest(),'bytes':size}),flush=True)


if __name__ == '__main__':
    main()
