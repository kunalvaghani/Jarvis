import sys
import json


x = json.load(sys.stdin)
result = (x*9/5)+32
print(json.dumps(result))
