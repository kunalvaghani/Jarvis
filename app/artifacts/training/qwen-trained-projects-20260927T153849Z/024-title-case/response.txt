import sys
import json

x = json.load(sys.stdin)
result = (str(x).title())
print(json.dumps(result))
