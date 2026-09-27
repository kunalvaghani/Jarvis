import json
import sys

def is_prime(n):
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps({"error": "Input must be a JSON array"}), file=sys.stderr)
            sys.exit(1)
        
        n = int(input_data[0])
        primes = [p for p in range(2, n + 1) if is_prime(p)]
        print(json.dumps(primes))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        sys.exit(1)
    except ValueError:
        print(json.dumps({"error": "First element must be an integer"}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()