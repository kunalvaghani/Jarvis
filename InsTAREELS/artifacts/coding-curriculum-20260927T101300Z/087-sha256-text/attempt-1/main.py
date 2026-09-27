import json
import sys
import hashlib

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        return
    
    if not isinstance(input_data, str):
        print(json.dumps(None), file=sys.stderr)
        return
    
    try:
        text = input_data.lower()
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        print(digest)
    except Exception:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()