import sys
import json


x = json.load(sys.stdin)
result = (lambda x: ([*x] if isinstance(x,list) else x))(x)
print(json.dumps(result))
