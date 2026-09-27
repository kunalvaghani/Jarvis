import sys
import json

x = json.load(sys.stdin)
result = (x[0] if x else 1) * (x[1] if x else 1) * (x[2] if x else 1)
print(json.dumps(result))
