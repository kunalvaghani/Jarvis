import sys
import json

x = json.load(sys.stdin)
result = (int(x,2))
print(json.dumps(result))
