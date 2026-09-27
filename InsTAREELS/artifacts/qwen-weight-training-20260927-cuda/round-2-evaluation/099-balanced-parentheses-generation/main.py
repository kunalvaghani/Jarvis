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
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, int) or input_data < 0:
            print(json.dumps([]), file=sys.stderr)
            return
        n = input_data
        if n < 0:
            print(json.dumps([]), file=sys.stderr)
            return
        result = generate_parentheses(n)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()