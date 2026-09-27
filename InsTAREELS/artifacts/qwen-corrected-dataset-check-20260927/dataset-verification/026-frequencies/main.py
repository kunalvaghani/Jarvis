import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps({}), file=sys.stderr)
            return
        frequency_map = {}
        for item in input_data:
            if isinstance(item, str):
                frequency_map[item] = frequency_map.get(item, 0) + 1
        print(json.dumps(frequency_map))
    except json.JSONDecodeError as e:
        print(json.dumps({}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()