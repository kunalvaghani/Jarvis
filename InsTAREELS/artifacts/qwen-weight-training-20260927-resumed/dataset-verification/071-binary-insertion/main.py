import sys
import bisect
import json


x = json.load(sys.stdin)
result = (bisect.bisect_left(*x))
print(json.dumps(result))
