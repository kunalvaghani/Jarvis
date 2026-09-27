import json
import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps({"error": "Invalid input format. Expected [list, positive_int]"}), file=sys.stderr)
            sys.exit(1)
        
        values = data[0]
        window_size = data[1]
        
        if not isinstance(values, list):
            print(json.dumps({"error": "First element must be a list"}), file=sys.stderr)
            sys.exit(1)
        
        if not isinstance(window_size, int) or window_size <= 0:
            print(json.dumps({"error": "Second element must be a positive integer"}), file=sys.stderr)
            sys.exit(1)
        
        result = []
        for i in range(len(values) - window_size + 1):
            window = values[i:i+window_size]
            mean_val = sum(window) / len(window)
            result.append(mean_val)
        
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()