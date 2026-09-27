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
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        coefficients, x = input_data[0], input_data[1]
        
        if not isinstance(coefficients, list) or not isinstance(x, (int, float)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        result = evaluate_polynomial(coefficients, x)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()