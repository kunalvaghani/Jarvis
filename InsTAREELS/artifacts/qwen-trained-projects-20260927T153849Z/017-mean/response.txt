import sys
import json


x = json.load(sys.stdin)
result = (sum(x) / len(x))
print(json.dumps(result))
