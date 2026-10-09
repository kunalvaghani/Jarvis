import sys
import base64

x = json.load(sys.stdin)
result = (base64.b64decode(x))
print(json.dumps(result))
