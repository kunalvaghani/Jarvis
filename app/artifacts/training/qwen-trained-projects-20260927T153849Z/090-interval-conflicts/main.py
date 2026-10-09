import sys
import json


def find_overlapping_intervals(intervals):
    result = []
    for i in range(len(intervals)):
        for j in range(i+1, len(intervals)):
            if intervals[i][1] >= intervals[j][0]:
                result.append([min(intervals[i][0], intervals[j][0]), max(intervals[i][1], intervals[j][1])])
    return sorted(result)


def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps([]))
            return
        
        intervals = data[0]
        result = find_overlapping_intervals(intervals)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)


if __name__ == "__main__":
    main()