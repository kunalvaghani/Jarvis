import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.stderr.write("Error: Invalid JSON input\n")
        sys.exit(1)
    
    if not isinstance(input_data, list):
        sys.stderr.write("Error: Input must be a list\n")
        sys.exit(1)
    
    try:
        values = [float(x) for x in input_data]
    except (ValueError, TypeError):
        sys.stderr.write("Error: All elements must be numeric\n")
        sys.exit(1)
    
    if len(values) == 0:
        print(json.dumps([]))
        return
    
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val
    
    if range_val == 0:
        result = [0.0] * len(values)
    else:
        result = [(v - min_val) / range_val for v in values]
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()