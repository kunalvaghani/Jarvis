import sys
import json


x = json.load(sys.stdin)
result = (x[0]*x[1]*x[2]/100)
print(json.dumps(result))
