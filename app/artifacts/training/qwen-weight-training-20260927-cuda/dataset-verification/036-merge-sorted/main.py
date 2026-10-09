import json
import sys

def merge_sorted_lists(lists):
    if not lists or len(lists) != 2:
        return []
    
    list1 = lists[0]
    list2 = lists[1]
    
    result = []
    i, j = 0, 0
    
    while i < len(list1) and j < len(list2):
        if list1[i] <= list2[j]:
            result.append(list1[i])
            i += 1
        else:
            result.append(list2[j])
            j += 1
    
    result.extend(list1[i:])
    result.extend(list2[j:])
    
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