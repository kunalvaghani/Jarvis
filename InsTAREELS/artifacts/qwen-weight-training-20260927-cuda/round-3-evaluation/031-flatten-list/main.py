import json
import sys

def flatten(lst):
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    print(json.dumps(None), file=sys.stderr)
    sys.exit(1)

if not isinstance(input_data, list):
    print(json.dumps(None), file=sys.stderr)
    sys.exit(1)

flattened = flatten(input_data)
print(json.dumps(flattened))