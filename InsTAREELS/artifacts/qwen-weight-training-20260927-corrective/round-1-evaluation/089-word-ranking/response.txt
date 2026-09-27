import sys
import json


x = json.load(sys.stdin)
result = (sorted(([(i,j) for i in x for j in i.split() if j]), key=lambda x:(-x[1],x[0])))
print(json.dumps(result))
