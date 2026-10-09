import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps({"error": "Input must be a JSON array"}), file=sys.stderr)
            sys.exit(1)
        
        seen = set()
        result = []
        for item in input_data:
            if isinstance(item, int) and item not in seen:
                seen.add(item)
                result.append(item)
        
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()