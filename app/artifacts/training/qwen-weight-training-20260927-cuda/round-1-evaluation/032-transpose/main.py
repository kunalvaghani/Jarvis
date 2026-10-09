import json
import sys

def transpose(matrix):
    if not matrix:
        return []
    return list(map(list, zip(*matrix)))

if __name__ == "__main__":
    try:
        data = json.load(sys.stdin)
        result = transpose(data)
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps([]))