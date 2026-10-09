import sys
import json


x = json.load(sys.stdin)
result = (x[0]*x[1]/2)
print(json.dumps(result))
