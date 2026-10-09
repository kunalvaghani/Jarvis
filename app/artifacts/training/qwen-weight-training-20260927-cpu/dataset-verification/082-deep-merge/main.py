import json
import sys

def deep_merge(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        result = left.copy()
        for key, value in right.items():
            if key in result:
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    elif isinstance(left, list) and isinstance(right, list):
        return [deep_merge(l, r) for l, r in zip(left, right)]
    else:
        return right

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps({"error": "Input must be a list of exactly two JSON values"}), file=sys.stderr)
            sys.exit(1)
        left, right = input_data
        result = deep_merge(left, right)
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()