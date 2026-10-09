import sys
import json


def flatten(x):
    if isinstance(x, list):
        return [item for sublist in x for item in flatten(sublist)]
    else:
        return [x]


result = (json.dumps(flatten(json.load(sys.stdin))))
print(result)
