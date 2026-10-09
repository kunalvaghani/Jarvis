import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(None), file=sys.stderr)
        return
    
    if not isinstance(input_data, list) or len(input_data) != 2:
        print(json.dumps(None), file=sys.stderr)
        return
    
    x, y = input_data
    
    if not isinstance(x, int) or not isinstance(y, list):
        print(json.dumps(None), file=sys.stderr)
        return
    
    if len(x) != 1 or len(y) != 2:
        print(json.dumps(None), file=sys.stderr)
        return
    
    n = x[0]
    keys = y[0]
    
    if not isinstance(n, int) or not isinstance(keys, list):
        print(json.dumps(None), file=sys.stderr)
        return
    
    if len(keys) != len(set(keys)):
        print(json.dumps(None), file=sys.stderr)
        return
    
    hits = 0
    keys.sort()
    
    for key in keys:
        if key in keys[:len(keys)-1]:
            hits += 1
    
    result = {"hits": hits, "keys": keys}
    print(json.dumps(result))

if __name__ == "__main__":
    main()