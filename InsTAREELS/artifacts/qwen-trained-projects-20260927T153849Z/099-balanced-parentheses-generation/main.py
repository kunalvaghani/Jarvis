import sys
import itertools

def generate_parentheses(n):
    if n < 0:
        return []
    if n == 0:
        return ["()"]
    result = []
    for i in range(1, n+1):
        for subset in generate_parentheses(i-1):
            for j in range(len(subset)+1):
                result.append(f"({subset[:j]}{subset[j:]})")
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
        
        result = generate_parentheses(n)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()