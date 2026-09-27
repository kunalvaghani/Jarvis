import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(1), file=sys.stderr)
            return
        result = 1
        for item in input_data:
            if isinstance(item, (int, float)):
                result *= item
            elif isinstance(item, list):
                result *= product(item)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(1), file=sys.stderr)

if __name__ == "__main__":
    main()