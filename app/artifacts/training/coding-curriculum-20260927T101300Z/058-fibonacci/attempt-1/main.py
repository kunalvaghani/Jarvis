import json
import sys

def fibonacci(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        value = json.loads(input_data)
        result = fibonacci(value)
        print(json.dumps(result))
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()