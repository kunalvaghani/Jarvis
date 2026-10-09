import sys
import bisect


x = json.load(sys.stdin)
result = (bisect.bisect_left(x[0],x[1]))
print(json.dumps(result))
