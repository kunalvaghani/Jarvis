import sys
import json

def process(input_str):
    try:
        result = (x for x in input_str if x.isalnum())
        return (x.replace(" ", "-").lower() for x in result)
    except Exception as e:
        return None

try:
    input_data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(1)

result = process(input_data)
if result is not None:
    print(json.dumps(result))
else:
    sys.exit(0)