import json
import sys

def merge_dicts(d1, d2):
    if isinstance(d1, dict) and isinstance(d2, dict):
        merged = {}
        for key in set(d1.keys()) | set(d2.keys()):
            if key in d1:
                merged[key] = merge_dicts(d1[key], d2[key])
            elif key in d2:
                merged[key] = merge_dicts(d1, d2[key])
        return merged
    else:
        return d1 or d2

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        
        result = []
        for item in input_data:
            if isinstance(item, dict):
                merged = merge_dicts(item, {})
                result.append(merged)
            else:
                result.append(item)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()