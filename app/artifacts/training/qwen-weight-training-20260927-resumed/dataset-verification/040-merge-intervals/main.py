import json
import sys

def merge_intervals(intervals):
    if not intervals:
        return []
    
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]
    
    for current in sorted_intervals[1:]:
        last = merged[-1]
        if current[0] <= last[1]:
            merged[-1] = [last[0], max(last[1], current[1])]
        else:
            merged.append(current)
    
    return merged

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        intervals = json.loads(input_data)
        result = merge_intervals(intervals)
        print(json.dumps(result))
    except json.JSONDecodeError:
        pass
    except Exception:
        pass

if __name__ == "__main__":
    main()