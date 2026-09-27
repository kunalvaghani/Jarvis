import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print("Error: No input provided.", file=sys.stderr)
            sys.exit(1)
        
        data = json.loads(input_data)
        if not isinstance(data, list) or len(data) != 2:
            print("Error: Input must be a JSON array with exactly two numbers.", file=sys.stderr)
            sys.exit(1)
        
        num1, num2 = data[0], data[1]
        result = num1 + num2
        
        print(result)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()