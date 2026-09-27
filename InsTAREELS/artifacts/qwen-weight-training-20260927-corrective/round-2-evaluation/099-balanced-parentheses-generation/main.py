import sys
import itertools
import json

def generate_parentheses(n):
    if n < 0:
        return []
    if n == 0:
        return [""]
    result = []
    for length in range(1, n + 1):
        for subset in itertools.combinations(range(length), length // 2):
            result.append("(" + "".join(subset) + ")")
    return sorted(result)

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        n = int(input_data)
        if n < 0:
            print(json.dumps([]))
            return
        
        parentheses = generate_parentheses(n)
        print(json.dumps(parentheses))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()