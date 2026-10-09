import json
import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(True))
            return
        
        parsed = json.loads(input_data)
        
        def validate_brackets(data):
            stack = []
            mapping = {')': '(', ']': '[', '}': '{'}
            
            for char in data:
                if char in mapping.values():
                    stack.append(char)
                elif char in mapping:
                    if not stack or stack[-1] != mapping[char]:
                        return False
                    stack.pop()
            return len(stack) == 0
        
        result = validate_brackets(parsed)
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps(True))
    except Exception:
        print(json.dumps(True))

if __name__ == "__main__":
    main()