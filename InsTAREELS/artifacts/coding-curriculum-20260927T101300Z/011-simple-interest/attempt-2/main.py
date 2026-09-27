import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 3:
            print(json.dumps({"error": "Input must be a JSON array with exactly three numeric values."}), file=sys.stderr)
            sys.exit(1)
        
        principal = input_data[0]
        annual_percent = input_data[1]
        years = input_data[2]
        
        if not all(isinstance(x, (int, float)) for x in [principal, annual_percent, years]):
            print(json.dumps({"error": "All values must be numeric."}), file=sys.stderr)
            sys.exit(1)
        
        interest = principal * (annual_percent / 100) * years
        output = {"interest": interest}
        print(json.dumps(output))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input."}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()