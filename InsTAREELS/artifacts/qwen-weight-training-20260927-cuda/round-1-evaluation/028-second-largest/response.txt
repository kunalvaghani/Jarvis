import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(json.dumps(None))
            return
        if len(data) < 2:
            print(json.dumps(None))
            return
        distinct_values = set(data)
        if len(distinct_values) < 2:
            print(json.dumps(None))
            return
        return json.dumps(max(distinct_values))
    except json.JSONDecodeError:
        print(json.dumps(None))
        return

if __name__ == "__main__":
    main()