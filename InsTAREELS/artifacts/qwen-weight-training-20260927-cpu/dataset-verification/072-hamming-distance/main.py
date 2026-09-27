import json
import sys

def hamming_distance(s1: str, s2: str) -> int:
    if len(s1) != len(s2):
        return -1
    distance = 0
    for c1, c2 in zip(s1, s2):
        if c1 != c2:
            distance += 1
    return distance

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        s1, s2 = input_data
        if not isinstance(s1, str) or not isinstance(s2, str):
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        result = hamming_distance(str(s1), str(s2))
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()