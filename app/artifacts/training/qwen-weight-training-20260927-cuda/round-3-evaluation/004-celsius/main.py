import json
import sys

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
    sys.exit(1)

if not isinstance(input_data, dict) or "value" not in input_data:
    print(json.dumps({"error": "Invalid input format"}), file=sys.stderr)
    sys.exit(1)

try:
    value = float(input_data["value"])
except ValueError:
    print(json.dumps({"error": "Invalid input value"}), file=sys.stderr)
    sys.exit(1)

result = celsius_to_fahrenheit(value)
print(result)