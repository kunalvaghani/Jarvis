import sys
import json


x = json.load(sys.stdin)
result = (x[0]*(1+x[1]/100))
print(json.dumps(result))
