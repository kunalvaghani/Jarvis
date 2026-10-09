import sys
import json


x = json.load(sys.stdin)
result = (sorted((list(set([i.split() for i in x if i])),-len(i)) for i in x))
print(json.dumps(result))
