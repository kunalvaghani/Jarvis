import json
import sys

try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(1)

if not isinstance(data, list) or len(data) != 2:
    sys.exit(1)

width, height = data

if not (isinstance(width, (int, float)) and isinstance(height, (int, float))):
    sys.exit(1)

area = width * height
print(area)
