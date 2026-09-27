import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps([]), file=sys.stderr)
            return
        
        result = []
        seen = set()
        
        for x in input_data:
            if isinstance(x, int) and x not in seen:
                seen.add(x)
                result.append(x)
        
        print(json.dumps(result))
    except (json.JSONDecodeError, ValueError):
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()