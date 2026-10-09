import sys
import itertools
import json


x = json.load(sys.stdin)
result = (sorted({tuple(sorted(t)) for t in itertools.combinations(x,3) if sum(t)==0}))
print(json.dumps(result))
