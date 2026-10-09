import sys
import base64
import json


x = json.load(sys.stdin)
result = (base64.b64encode(x.encode()).decode())
print(json.dumps(result))
