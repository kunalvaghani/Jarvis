import sys
import json

x = json.load(sys.stdin)
result = (sum(1 for i in x if i > 0))
print(json.dumps(result))
