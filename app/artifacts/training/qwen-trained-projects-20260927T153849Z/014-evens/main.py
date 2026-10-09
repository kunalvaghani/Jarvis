import sys
import json

def process(x):
    return x if (x % 2 == 0) else None

result = (json.dumps(process(json.load(sys.stdin))))
print(result)
