import sys
import itertools
import json


x = json.load(sys.stdin)
result = (sorted(list(itertools.combinations(x[0],x[1]))))
print(json.dumps(result))
