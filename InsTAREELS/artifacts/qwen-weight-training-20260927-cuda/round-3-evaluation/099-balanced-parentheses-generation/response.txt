import json
import sys

def is_balanced(s):
    balance = 0
    for char in s:
        if char == '(':
            balance += 1
        elif char == ')':
            balance -= 1
        if balance < 0:
            return False
    return balance == 0

def generate_parentheses(n):
    if n < 0:
        return []
    result = []
    def backtrack(path, left, right):
        if len(path) == 2 * n:
            result.append(''.join(path))
            return
        if left > right:
            return
        path.append('(')
        backtrack(path, left + 1, right)
        path.pop()
        path.append(')')
        backtrack(path, left, right + 1)
        path.pop()
    backtrack([], 0, 0)
    return result

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
        pairs = generate_parentheses(n)
        print(json.dumps(pairs))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()