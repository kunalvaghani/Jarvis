import json
import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            return
        
        data = json.loads(input_data)
        coefficients, value = data[0], data[1]
        
        result = 0
        for i, coeff in enumerate(coefficients):
            result += coeff * (value ** i)
        
        print(result)
    except Exception:
        pass

if __name__ == "__main__":
    main()