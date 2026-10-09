import json
import sys

def rotate_right(lst, k):
    if not lst:
        return []
    n = len(lst)
    if k <= 0:
        return lst
    k = k % n
    if k == 0:
        return lst
    return lst[-k:] + lst[:-k]

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        if len(input_data) < 2:
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        lst = input_data[0]
        k = input_data[1]
        result = rotate_right(lst, k)
        print(json.dumps(result))
    except (json.JSONDecodeError, IndexError, TypeError):
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()