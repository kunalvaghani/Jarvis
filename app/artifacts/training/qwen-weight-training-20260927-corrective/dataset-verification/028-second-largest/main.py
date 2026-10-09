import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps(None))
        return

    if not isinstance(data, list):
        print(json.dumps(None))
        return

    distinct_values = set(data)

    if len(distinct_values) < 2:
        print(json.dumps(None))
        return

    sorted_values = sorted(distinct_values, reverse=True)
    second_largest = sorted_values[1]

    print(json.dumps(second_largest))

if __name__ == "__main__":
    main()