import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps({"error": "Input must be a list"}), file=sys.stderr)
            return
        
        tokens = input_data
        stack = []
        
        for token in tokens:
            if isinstance(token, str):
                try:
                    num = float(token)
                except ValueError:
                    print(json.dumps({"error": f"Invalid number: {token}"}), file=sys.stderr)
                    return
                stack.append(num)
            elif isinstance(token, (int, float)):
                stack.append(float(token))
            elif token in "+-*/":
                if len(stack) < 2:
                    print(json.dumps({"error": "Insufficient operands for operator"}), file=sys.stderr)
                    return
                b = stack.pop()
                a = stack.pop()
                try:
                    if token == "+":
                        result = a + b
                    elif token == "-":
                        result = a - b
                    elif token == "*":
                        result = a * b
                    elif token == "/":
                        if b == 0:
                            print(json.dumps({"error": "Division by zero"}), file=sys.stderr)
                            return
                        result = a / b
                    else:
                        print(json.dumps({"error": f"Unknown operator: {token}"}), file=sys.stderr)
                        return
                    stack.append(result)
                except ZeroDivisionError:
                    print(json.dumps({"error": "Division by zero"}), file=sys.stderr)
                    return
            else:
                print(json.dumps({"error": f"Invalid token: {token}"}), file=sys.stderr)
                return
        
        if len(stack) != 1:
            print(json.dumps({"error": "Expected exactly one result"}), file=sys.stderr)
            return
        
        result = stack[0]
        print(result)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()