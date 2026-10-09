import sys
import json


x = json.load(sys.stdin)
result = (sum((int(d2)-int(d1)) for d1,d2 in zip(*x)))
print(json.dumps(result))
