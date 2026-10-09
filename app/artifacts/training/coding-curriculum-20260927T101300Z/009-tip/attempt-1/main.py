import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, dict):
            print(json.dumps({"error": "Input must be a JSON object"}), file=sys.stderr)
            sys.exit(1)
        
        bill = input_data.get("bill")
        tip_percent = input_data.get("tip_percent", 0)
        
        if not isinstance(bill, (int, float)) or bill < 0:
            print(json.dumps({"error": "Bill must be a non-negative number"}), file=sys.stderr)
            sys.exit(1)
        
        if not isinstance(tip_percent, (int, float)) or tip_percent < 0:
            print(json.dumps({"error": "Tip percentage must be a non-negative number"}), file=sys.stderr)
            sys.exit(1)
        
        total = bill + (bill * tip_percent / 100)
        result = {"total": round(total, 2)}
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()