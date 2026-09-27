import sys
import hashlib
import json


x = json.load(sys.stdin)
result = (hashlib.sha256(x.encode()).hexdigest())
print(json.dumps(result))
