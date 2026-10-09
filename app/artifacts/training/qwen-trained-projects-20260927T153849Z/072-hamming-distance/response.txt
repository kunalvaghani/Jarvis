import sys
import json


x = json.load(sys.stdin)
result = (len(x[0]) != len(x[1])) and (x[0].count(x[1]) == len(x[0]))
print(json.dumps(result))
