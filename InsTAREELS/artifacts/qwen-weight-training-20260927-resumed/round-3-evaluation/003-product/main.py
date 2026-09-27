import sys
import json


x = json.load(sys.stdin)
result = (reduce(lambda x,y:x*y,x))
print(json.dumps(result))
