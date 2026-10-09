import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(0), file=sys.stderr)
        return
    
    if not isinstance(data, list):
        print(json.dumps(0), file=sys.stderr)
        return
    
    n = len(data)
    if n == 0:
        print(json.dumps(0))
        return
    
    lis_length = 1
    prev = data[0]
    
    for i in range(1, n):
        if data[i] > prev:
            lis_length += 1
            prev = data[i]
    
    print(json.dumps(lis_length))

if __name__ == "__main__":
    main()