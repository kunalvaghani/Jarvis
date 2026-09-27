import sys
import json


x = json.load(sys.stdin)
result = ([list(row) for row in (zip(*x))])
print(json.dumps(result))
