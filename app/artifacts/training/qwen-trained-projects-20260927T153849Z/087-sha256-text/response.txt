import sys
import hashlib
import json

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        x = json.loads(input_data)
        if not isinstance(x, str):
            print(json.dumps(None))
            return
        
        result = hashlib.sha256(x.encode()).hexdigest()
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()