import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(json.dumps([data]), file=sys.stderr)
            return
        result = []
        for item in data:
            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps([]), file=sys.stderr)