import sys
import json


x = json.load(sys.stdin)
result = (sum((int(d)-int(s)) for s,d in zip(x[0].split('-'),x[1].split('-'))))
print(json.dumps(result))
