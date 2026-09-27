import sys
import itertools
import json


x = json.load(sys.stdin)
result = (sorted({tuple(sorted(c)) for c in itertools.combinations(x[0],x[1])}))
print(json.dumps(result))
