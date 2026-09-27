import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        
        if len(input_data) == 0:
            print(json.dumps(0))
            return
        
        max_val = max(input_data)
        min_val = min(input_data)
        result = max_val - min_val
        
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()