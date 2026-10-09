import sys
import json


x = json.load(sys.stdin)
result = ([[i,j] for i,a in enumerate(x) for j,b in enumerate(x) if i<j and max(a[0],b[0])<=min(a[1],b[1])])
print(json.dumps(result))
