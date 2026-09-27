import sys
import json


x = json.load(sys.stdin)
result = (x[0]-min(x))/(max(x)-min(x))
print(json.dumps(result))
