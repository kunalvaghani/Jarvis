import sys
import itertools
import json


x = json.load(sys.stdin)
result = (sorted([sorted(c) for n in range(len(x)+1) for c in itertools.combinations(x,n)]))
print(json.dumps(result))
