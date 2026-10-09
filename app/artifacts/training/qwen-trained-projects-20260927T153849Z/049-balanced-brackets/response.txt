import sys
import json

def validate(s):
    try:
        eval(s)
        return True
    except (SyntaxError, TypeError):
        return False

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        return
    
    if not isinstance(input_data, str):
        print(json.dumps(None), file=sys.stderr)
        return
    
    result = None
    try:
        result = validate(input_data)
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)
        return
    
    if result is None:
        print(json.dumps(None))
        return
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()