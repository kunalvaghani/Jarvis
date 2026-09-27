import json
import sys

def flatten(obj):
    result = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, list):
                result[key] = value
            elif isinstance(value, dict):
                flattened = flatten(value)
                for k, v in flattened.items():
                    result[f"{key}.{k}"] = v
            else:
                result[key] = value
    return result

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(1)

output = flatten(input_data)
print(json.dumps(output))