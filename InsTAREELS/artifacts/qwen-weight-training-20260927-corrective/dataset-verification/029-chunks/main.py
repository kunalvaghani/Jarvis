import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        items, chunk_size = input_data
        if not isinstance(items, list) or not isinstance(chunk_size, int) or chunk_size <= 0:
            print(json.dumps(None), file=sys.stderr)
            return
        
        result = []
        for i in range(0, len(items), chunk_size):
            result.append(items[i:i + chunk_size])
        
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()