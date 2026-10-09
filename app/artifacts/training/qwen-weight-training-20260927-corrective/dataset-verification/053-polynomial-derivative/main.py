import sys
import json


x = json.load(sys.stdin)
result = ([i*c for i,c in enumerate(x) if i])
print(json.dumps(result))
