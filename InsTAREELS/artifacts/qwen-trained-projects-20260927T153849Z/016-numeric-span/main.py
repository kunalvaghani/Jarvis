import sys
import json


x = json.load(sys.stdin)
result = (max(x) - min(x))
print(json.dumps(result))
