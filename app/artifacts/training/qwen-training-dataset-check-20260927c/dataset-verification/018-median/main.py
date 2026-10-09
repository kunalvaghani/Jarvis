import json
import sys

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list):
            print(json.dumps({"error": "Input must be a list"}), file=sys.stderr)
            sys.exit(1)
        
        if len(data) == 0:
            print(json.dumps({"error": "Input list is empty"}), file=sys.stderr)
            sys.exit(1)
        
        for item in data:
            if not isinstance(item, (int, float)):
                print(json.dumps({"error": "All items must be numeric"}), file=sys.stderr)
                sys.exit(1)
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        mid = n // 2
        
        if n % 2 == 0:
            median = (sorted_data[mid - 1] + sorted_data[mid]) / 2
        else:
            median = sorted_data[mid]
        
        print(json.dumps(median))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()