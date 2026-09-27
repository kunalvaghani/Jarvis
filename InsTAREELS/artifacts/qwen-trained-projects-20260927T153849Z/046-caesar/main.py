import sys
import json

def process(x):
    if isinstance(x, str):
        return chr((ord(x) - ord('a') + x[1]) % 26 + ord('a'))
    elif isinstance(x, int):
        return chr((x - ord('a') + x) % 26 + ord('a'))
    else:
        return x

result = (json.dumps(process(json.load(sys.stdin))))
print(result)
