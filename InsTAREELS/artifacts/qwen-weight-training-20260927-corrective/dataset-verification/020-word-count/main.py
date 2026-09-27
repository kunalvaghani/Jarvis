import sys
import json


x = json.load(sys.stdin)
result = (len(x.split()))
print(json.dumps(result))
