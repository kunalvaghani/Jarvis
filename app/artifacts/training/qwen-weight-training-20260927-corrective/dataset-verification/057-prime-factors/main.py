import json
import sys

def prime_factors(n):
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        value = json.loads(input_data)
        if not isinstance(value, int) or value < 1:
            print(json.dumps([]))
            return
        result = prime_factors(value)
        print(json.dumps(result))
    except Exception:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()