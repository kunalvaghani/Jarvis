import sys
import json


x = json.load(sys.stdin)
result = (x[::-1])
print(json.dumps(result))
