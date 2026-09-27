import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 1:
            print(json.dumps([]), file=sys.stderr)
            return
        
        x = input_data[0]
        if not isinstance(x, (int, float)):
            print(json.dumps([]), file=sys.stderr)
            return
        
        result = []
        for i in range(1, len(x)+1):
            coeff = (x**i - 1)/(i-1)
            result.append(coeff)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()