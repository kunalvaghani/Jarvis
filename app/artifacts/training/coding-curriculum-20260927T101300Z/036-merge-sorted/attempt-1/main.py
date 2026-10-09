import json
import sys

def merge_sorted_lists(lists):
    result = []
    i, j = 0, 0
    while i < len(lists[0]) and j < len(lists[1]):
        if lists[i] <= lists[j]:
            result.append(lists[i])
            i += 1
        else:
            result.append(lists[j])
            j += 1
    result.extend(lists[i:])
    return result

if __name__ == "__main__":
    input_data = sys.stdin.read()
    try:
        parsed = json.loads(input_data)
        if not isinstance(parsed, list) or len(parsed) != 2:
            print(json.dumps({"error": "Input must be a list of exactly two lists"}), file=sys.stderr)
            sys.exit(1)
        merged = merge_sorted_lists(parsed)
        print(json.dumps(merged))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)