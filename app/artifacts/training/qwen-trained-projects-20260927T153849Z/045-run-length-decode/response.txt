import sys
import json

def decode(s):
    result = []
    for char, count in s:
        result.extend([char * count])
    return ''.join(result)

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(None), file=sys.stderr)
        return
    
    if not isinstance(input_data, list) or len(input_data) != 1:
        print(json.dumps(None), file=sys.stderr)
        return
    
    s = input_data[0]
    if not isinstance(s, list) or len(s) != 2:
        print(json.dumps(None), file=sys.stderr)
        return
    
    result = decode(s)
    print(json.dumps(result))

if __name__ == "__main__":
    main()