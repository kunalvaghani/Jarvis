import sys
import json


x = json.load(sys.stdin)
result = sorted(x)
print(json.dumps(result))
