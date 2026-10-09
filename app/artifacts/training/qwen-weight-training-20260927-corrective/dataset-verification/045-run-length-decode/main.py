import sys
import json


x = json.load(sys.stdin)
result = ("".join(c*n for c,n in x))
print(json.dumps(result))
