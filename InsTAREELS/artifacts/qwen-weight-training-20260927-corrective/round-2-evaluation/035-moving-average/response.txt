import sys
import json


x = json.load(sys.stdin)
result = (lambda l,p: sum([i*(i+1)/2 for i in l[p-1]:i<p+1]))(*x)
print(json.dumps(result))
