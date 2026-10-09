import sys
import json


def merge(x, y):
    if isinstance(x, dict) and isinstance(y, dict):
        return {k: merge(v, w) for k, v in x.items() if k in y}
    elif isinstance(x, list) and isinstance(y, list):
        return [merge(a, b) for a, b in zip(x, y)]
    else:
        return x


x = json.load(sys.stdin)
result = merge(x, {})
print(json.dumps(result))
