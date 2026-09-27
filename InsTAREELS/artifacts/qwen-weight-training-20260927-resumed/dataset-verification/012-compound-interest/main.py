import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 3:
            print(json.dumps({"error": "Input must be a list of exactly three values."}), file=sys.stderr)
            sys.exit(1)
        
        principal = input_data[0]
        annual_percent = input_data[1]
        years = input_data[2]
        
        if not isinstance(principal, (int, float)) or not isinstance(annual_percent, (int, float)) or not isinstance(years, int):
            print(json.dumps({"error": "Principal and annual percent must be numeric; years must be an integer."}), file=sys.stderr)
            sys.exit(1)
        
        if principal < 0 or annual_percent < 0 or years < 0:
            print(json.dumps({"error": "Values must be non-negative."}), file=sys.stderr)
            sys.exit(1)
        
        final_balance = principal * ((1 + annual_percent / 100) ** years)
        
        print(json.dumps(final_balance))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input."}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()