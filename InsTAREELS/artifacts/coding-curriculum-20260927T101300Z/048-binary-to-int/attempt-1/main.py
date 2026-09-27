import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps({"error": "Input must be a list"}), file=sys.stderr)
            return
        
        binary_str = input_data[0]
        if not isinstance(binary_str, str):
            print(json.dumps({"error": "First element must be a string"}), file=sys.stderr)
            return
        
        try:
            result = int(binary_str, 2)
            print(result)
        except ValueError as e:
            print(json.dumps({"error": f"Invalid binary string: {e}"}), file=sys.stderr)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)

if __name__ == "__main__":
    main()