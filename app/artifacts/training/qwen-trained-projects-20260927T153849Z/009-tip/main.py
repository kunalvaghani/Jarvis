import sys
import json

x = json.load(sys.stdin)
result = (x[0]*(1+x[1]/100)+x[0])
print(json.dumps(result))
