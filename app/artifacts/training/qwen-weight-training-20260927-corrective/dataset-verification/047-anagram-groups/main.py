import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return
    
    if not isinstance(input_data, list):
        print(json.dumps({"error": "Input must be a list"}), file=sys.stderr)
        return
    
    groups = []
    seen_keys = set()
    
    for item in input_data:
        if not isinstance(item, str):
            continue
        
        sorted_chars = ''.join(sorted(item))
        key = sorted_chars
        
        if key in seen_keys:
            continue
        
        seen_keys.add(key)
        group = []
        for s in input_data:
            if isinstance(s, str) and ''.join(sorted(s)) == key:
                group.append(s)
        
        group.sort()
        groups.append(group)
    
    groups.sort()
    
    print(json.dumps(groups))

if __name__ == "__main__":
    main()