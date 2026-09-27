import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(json.dumps([data]), file=sys.stderr)
            return
        result = []
        seen = set()
        for item in data:
            if isinstance(item, int) and item not in seen:
                seen.add(item)
                result.append(item)
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()