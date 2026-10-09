import sys
import json

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, str):
            return
        
        result = []
        for char in data:
            count = (data.count(char))
            result.append([char, count])
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()