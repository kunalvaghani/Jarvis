"""One-shot reviewed utility runner; not an arbitrary-code security sandbox."""
import json
import sys
from .utility_core import execute


def main():
    try:
        raw=sys.stdin.buffer.read(1000001)
        if len(raw)>1000000:raise ValueError('Utility request exceeds 1 MB.')
        request=json.loads(raw)
        result=execute(request['name'],request['root'],request['arguments'])
        text=json.dumps({'ok':True,'value':result},allow_nan=False)
        if len(text.encode())>1000000:raise ValueError('Utility result exceeds 1 MB.')
    except Exception as error:
        text=json.dumps({'ok':False,'error_type':type(error).__name__,'error':str(error)[:500]})
    print(text)


if __name__=='__main__':main()
