import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps({"error": "Invalid input: expected [sorted_list, target]"}), file=sys.stderr)
            sys.exit(1)
        
        sorted_list = data[0]
        target = data[1]
        
        if not isinstance(sorted_list, list):
            print(json.dumps({"error": "First element must be a list"}), file=sys.stderr)
            sys.exit(1)
        
        if not isinstance(target, (int, float)):
            print(json.dumps({"error": "Second element must be a number"}), file=sys.stderr)
            sys.exit(1)
        
        leftmost_index = None
        for i in range(len(sorted_list) + 1):
            if i == len(sorted_list):
                if sorted_list[-1] <= target:
                    break
            else:
                if sorted_list[i] > target:
                    break
            leftmost_index = i
        
        print(json.dumps(leftmost_index))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON decode error: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()