import sys
import json


x = json.load(sys.stdin)
result = (sum(x) if x else 0)
print(json.dumps(result))
