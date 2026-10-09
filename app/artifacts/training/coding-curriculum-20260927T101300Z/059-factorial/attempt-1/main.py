import json
import sys

try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(1)

if not isinstance(data, int):
    sys.exit(1)

if data < 0:
    sys.exit(1)

result = 1
for i in range(1, data + 1):
    result *= i

print(result)