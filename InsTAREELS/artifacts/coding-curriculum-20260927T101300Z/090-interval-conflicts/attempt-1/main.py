import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps([]), file=sys.stderr)
        return
    
    if not isinstance(input_data, list):
        print(json.dumps([]), file=sys.stderr)
        return
    
    intervals = []
    for i, item in enumerate(input_data):
        if isinstance(item, list) and len(item) == 2:
            try:
                start = int(item[0])
                end = int(item[1])
                if start <= end:
                    intervals.append((start, end, i))
                else:
                    print(json.dumps([]), file=sys.stderr)
                    return
            except (ValueError, TypeError):
                print(json.dumps([]), file=sys.stderr)
                return
    
    result = []
    for i in range(len(intervals)):
        for j in range(i + 1, len(intervals)):
            start_i, end_i, idx_i = intervals[i]
            start_j, end_j, idx_j = intervals[j]
            if start_i <= end_j or start_j <= end_i:
                result.append([idx_i, idx_j])
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()