import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps({"error": "Input must be a list of two elements."}), file=sys.stderr)
            return
        
        coefficients, value = input_data
        if not isinstance(coefficients, list) or len(coefficients) != len(value):
            print(json.dumps({"error": "Both coefficients and value must be lists of the same length."}), file=sys.stderr)
            return
        
        result = 0
        for i, coeff in enumerate(coefficients):
            if not isinstance(coeff, (int, float)):
                print(json.dumps({"error": f"Coefficient at index {i} is not a number."}), file=sys.stderr)
                return
            result += coeff * (value ** i)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()