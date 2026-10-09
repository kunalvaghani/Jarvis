import json
import sys

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps(0))
            return
        
        data = json.loads(input_data)
        
        if isinstance(data, list):
            count = sum(1 for item in data if isinstance(item, (int, float)) and item > 0)
        elif isinstance(data, dict):
            count = sum(1 for value in data.values() if isinstance(value, (int, float)) and value > 0)
        else:
            print(json.dumps(0))
            return
        
        print(json.dumps(count))
    except json.JSONDecodeError:
        print(json.dumps(0), file=sys.stderr)
    except Exception:
        print(json.dumps(0), file=sys.stderr)

if __name__ == "__main__":
    main()