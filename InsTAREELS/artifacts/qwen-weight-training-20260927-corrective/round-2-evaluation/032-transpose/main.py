import sys
import json


x = json.load(sys.stdin)
result = (lambda x: [[i for i in j] for j in zip(*x)]) (x)
print(json.dumps(result))
