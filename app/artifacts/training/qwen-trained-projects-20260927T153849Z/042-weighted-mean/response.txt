import sys
import json

def weighted_average(values):
    total_weight = sum(weight for _, weight in values)
    if total_weight == 0:
        return 0.0
    return sum(value * weight for value, weight in values) / total_weight

try:
    input_data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(1)

result = weighted_average(input_data)
print(json.dumps(result))
