import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, (int, float)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        celsius = input_data
        fahrenheit = (celsius * 9/5) + 32
        print(json.dumps(fahrenheit))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()