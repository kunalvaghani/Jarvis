import json
import sys
from itertools import combinations

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            return
        
        data = json.loads(input_data)
        
        if isinstance(data, list) and len(data) == 2:
            elements, k = data[0], data[1]
            
            if not isinstance(elements, list):
                print(json.dumps(None), file=sys.stderr)
                return
            
            if not isinstance(k, int):
                print(json.dumps(None), file=sys.stderr)
                return
            
            if k < 0 or k > len(elements):
                print(json.dumps(None), file=sys.stderr)
                return
            
            result = [list(c) for c in combinations(elements, k)]
            print(json.dumps(result))
        else:
            print(json.dumps(None), file=sys.stderr)
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
    except Exception:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()