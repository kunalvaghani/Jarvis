import json
import sys

def evaluate_polynomial(coefficients, x):
    result = 0
    for coeff, power in zip(coefficients, range(len(coefficients))):
        result += coeff * (x ** power)
    return result

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(input_data, list) or len(input_data) != 2:
        print(json.dumps({"error": "Invalid input format"}), file=sys.stderr)
        sys.exit(1)
    
    coefficients, x = input_data
    
    if not isinstance(coefficients, list) or not isinstance(x, (int, float)):
        print(json.dumps({"error": "Invalid input type"}), file=sys.stderr)
        sys.exit(1)
    
    if not (isinstance(x, int) or isinstance(x, float)):
        print(json.dumps({"error": "Invalid input type"}), file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(coefficients[0], list) or len(coefficients[0]) != 2:
        print(json.dumps({"error": "Invalid coefficient format"}), file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(coefficients[1], (int, float)):
        print(json.dumps({"error": "Invalid coefficient type"}), file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(coefficients[0][0], int) or isinstance(coefficients[0][0], float):
        print(json.dumps({"error": "Invalid coefficient value"}), file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(coefficients[0][1], int) or isinstance(coefficients[0][1], float):
        print(json.dumps({"error": "Invalid coefficient value"}), file=sys.stderr)
    
    if not isinstance(coefficients[1][0], int) or isinstance(coefficients[1][0], float):
        print(json.dumps({"error": "Invalid coefficient value"}), file=sys.stderr)
    
    if not isinstance(coefficients[1][1], int) or isinstance(coefficients[1][1], float):
        print(json.dumps({"error": "Invalid coefficient value"}), file=sys.stderr)
    
    result = evaluate_polynomial(coefficients, x)
    print(json.dumps(result))

if __name__ == "__main__":
    main()