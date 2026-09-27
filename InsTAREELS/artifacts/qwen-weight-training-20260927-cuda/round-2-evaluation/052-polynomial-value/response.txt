import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        coefficients, value = input_data
        
        if not isinstance(coefficients, list) or not isinstance(value, (int, float)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if len(coefficients) != len(set(coefficients)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        result = 0
        for i, coeff in enumerate(coefficients):
            result += coeff * (value ** i)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()