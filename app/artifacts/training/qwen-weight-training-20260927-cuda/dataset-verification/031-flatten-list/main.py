import json
import sys

def flatten_one_level(data):
    result = []
    for item in data:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result

try:
    input_data = json.load(sys.stdin)
    output_data = flatten_one_level(input_data)
    print(json.dumps(output_data))
except json.JSONDecodeError as e:
    sys.stderr.write(f"JSON decode error: {e}\n")
except Exception as e:
    sys.stderr.write(f"Error: {e}\n")
