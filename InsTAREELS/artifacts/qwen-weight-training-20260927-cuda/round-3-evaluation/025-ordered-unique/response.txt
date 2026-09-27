import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps([]), file=sys.stderr)
            return
        
        seen = set()
        result = []
        
        for item in input_data:
            if isinstance(item, int):
                if item in seen:
                    continue
                seen.add(item)
                result.append(item)
    
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()