import sys
import json
import math


x = json.load(sys.stdin)
result = ([p for p in range(2,x+1) if all(p%d for d in range(2,math.isqrt(p)+1))])
print(json.dumps(result))
