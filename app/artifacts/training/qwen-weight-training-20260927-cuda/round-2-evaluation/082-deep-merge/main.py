import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(input_data), file=sys.stderr)
            return
        
        result = {}
        for item in input_data:
            if isinstance(item, dict):
                merged = merge_dicts(item, result)
                result = merged
            else:
                result[item] = item
        
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)

def merge_dicts(dict1, dict2):
    merged = {}
    for key, value in dict1.items():
        if isinstance(value, dict):
            merged[key] = merge_dicts(value, merged.get(key, {}))
        else:
            merged[key] = value
    return merged

if __name__ == "__main__":
    main()