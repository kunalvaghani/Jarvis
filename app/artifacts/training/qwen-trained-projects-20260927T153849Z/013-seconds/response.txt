import sys
import json

x = json.load(sys.stdin)
result = (int(x['hours']),int(x['minutes']),int(x['seconds']))
print(json.dumps(result))
