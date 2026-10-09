import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps([]), file=sys.stderr)
            return
        
        result = []
        for i in range(len(input_data) - 1):
            result.append(input_data[i + 1])
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()