import json
import sys

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"error": "No input provided"}), file=sys.stderr)
            return
        
        parsed_input = json.loads(input_data)
        
        if isinstance(parsed_input, str):
            reversed_string = parsed_input[::-1]
            result = {"reversed": reversed_string}
        else:
            result = {"error": "Input must be a JSON string"}
        
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()