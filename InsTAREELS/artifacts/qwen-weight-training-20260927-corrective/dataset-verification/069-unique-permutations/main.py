import sys
import itertools
import json


x = json.load(sys.stdin)
result = (sorted(set(itertools.permutations(x))))
print(json.dumps(result))
