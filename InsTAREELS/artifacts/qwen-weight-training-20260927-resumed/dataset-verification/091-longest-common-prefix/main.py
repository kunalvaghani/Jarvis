import json
import sys

def longest_common_prefix(strings):
    if not strings:
        return ""
    
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            sys.exit(0)
        
        data = json.loads(input_data)
        result = longest_common_prefix(data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
