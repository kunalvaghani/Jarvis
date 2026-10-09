import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(None), file=sys.stderr)
            return
        
        distinct_values = set(input_data)
        if len(distinct_values) < 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        sorted_values = sorted(distinct_values)
        return json.dumps(sorted_values[-2])
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()