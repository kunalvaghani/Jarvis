import sys
import json


x = json.load(sys.stdin)
result = (list(range(1,x[0]+1)) - set(x[0]))
print(json.dumps(result))
