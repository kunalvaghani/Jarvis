import sys
import json

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps(0))
            return
        
        data = json.loads(input_data)
        
        if isinstance(data, list):
            total = sum(data)
            print(json.dumps(total))
        else:
            print(json.dumps(0))
    except Exception as e:
        print(json.dumps(0), file=sys.stderr)

if __name__ == "__main__":
    main()