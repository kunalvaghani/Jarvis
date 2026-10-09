import sys

def main():
    try:
        data = sys.stdin.read().strip()
        if not data:
            print(1)
            return
        value = json.loads(data)
        if isinstance(value, list):
            result = 1
            for item in value:
                if isinstance(item, (int, float)):
                    result *= item
                else:
                    raise ValueError("All items must be numeric")
            print(result)
        elif isinstance(value, (int, float)):
            print(value)
        else:
            raise ValueError("Input must be a number or list of numbers")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()