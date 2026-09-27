import sys
import math

def lcm(a, b):
    return abs(a*b) // math.gcd(a, b)

x = json.load(sys.stdin)
result = (lcm(x[0], x[1]))
print(json.dumps(result))
