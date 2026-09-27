import json
import sys

def prime_factors(n):
    factors = []
    divisor = 2
    while n > 1:
        while n % divisor == 0:
            factors.append(divisor)
            n //= divisor
        divisor += 1
    return factors

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps([]), file=sys.stderr)
        return
    
    if not isinstance(input_data, int) or input_data < 1:
        print(json.dumps([]), file=sys.stderr)
        return
    
    result = prime_factors(input_data)
    print(json.dumps(result))

if __name__ == "__main__":
    main()