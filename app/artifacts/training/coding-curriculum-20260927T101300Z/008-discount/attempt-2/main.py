import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        
        price = input_data.get("price")
        percentage = input_data.get("percentage")
        
        if not isinstance(price, (int, float)) or not isinstance(percentage, (int, float)):
            print(json.dumps({"error": "Price and percentage must be numbers"}), file=sys.stderr)
            sys.exit(1)
        
        discounted_price = price * (1 - percentage / 100)
        result = {"discounted_price": discounted_price}
        
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()