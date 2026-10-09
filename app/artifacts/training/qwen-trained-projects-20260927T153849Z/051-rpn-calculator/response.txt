import sys
import operator
import json

def eval_rpn(tokens):
    stack = []
    for token in tokens:
        if isinstance(token, (int, float)):
            stack.append(token)
        elif token == '+':
            b = stack.pop()
            a = stack.pop()
            stack.append(a + b)
        elif token == '-':
            b = stack.pop()
            a = stack.pop()
            stack.append(a - b)
        elif token == '*':
            b = stack.pop()
            a = stack.pop()
            stack.append(a * b)
        elif token == '/':
            b = stack.pop()
            a = stack.pop()
            if b == 0:
                raise ZeroDivisionError("Division by zero")
            stack.append(a / b)
        else:
            raise ValueError(f"Invalid token: {token}")
    return stack[0]

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            sys.exit(0)
        
        result = eval_rpn(json.loads(input_data))
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)