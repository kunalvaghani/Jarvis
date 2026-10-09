import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps({"error": "Input must be a list of exactly two integers."}), file=sys.stderr)
            sys.exit(1)
        
        a, b = data
        if not (isinstance(a, int) and isinstance(b, int)):
            print(json.dumps({"error": "Both elements must be integers."}), file=sys.stderr)
            sys.exit(1)
        
        if a < 0 or b < 0:
            print(json.dumps({"error": "Integers must be non-negative."}), file=sys.stderr)
            sys.exit(1)
        
        if a == 0 or b == 0:
            result = 0
        else:
            result = (a * b) // abs(a - b) if a != b else a
            if result < 0:
                result = -result
        
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()