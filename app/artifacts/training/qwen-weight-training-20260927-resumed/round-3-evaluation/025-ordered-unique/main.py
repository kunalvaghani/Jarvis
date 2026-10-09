import sys
import json


x = json.load(sys.stdin)
result = ([i for i in set(x)])
print(json.dumps(result))
