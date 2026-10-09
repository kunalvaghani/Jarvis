import sys
import json


x = json.load(sys.stdin)
result = (sum(x) if x else [])
print(json.dumps(result))
