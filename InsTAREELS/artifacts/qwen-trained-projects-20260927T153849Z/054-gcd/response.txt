import sys
import math

x = json.load(sys.stdin)
result = (math.gcd(x[0], x[1]))
print(json.dumps(result))
