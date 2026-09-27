import sys
import json


def merge_intervals(intervals):
    if not intervals:
        return []
    
    merged = []
    current = intervals[0]
    
    for interval in intervals[1:]:
        if current[1] < interval[0]:
            merged.append(current)
            current = interval
        else:
            current[1] = max(current[1], interval[1])
    
    merged.append(current)
    return merged


def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 1:
            print(json.dumps([]))
            return
        
        result = merge_intervals(data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)


if __name__ == "__main__":
    main()