import sys
import json


x = json.load(sys.stdin)
result = (lambda x: ({**x,**x[0]} if isinstance(x,dict) else x)(x))
print(json.dumps(result(x)))
