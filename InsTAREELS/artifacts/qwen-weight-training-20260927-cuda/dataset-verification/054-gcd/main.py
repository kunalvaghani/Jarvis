import json
import sys

def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        x, y = input_data
        if not (isinstance(x, int) and isinstance(y, int) and x >= 0 and y >= 0):
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        result = gcd(x, y)
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()