import sys
import json


x = json.load(sys.stdin)
result = ([item for sublist in x for item in (sublist if isinstance(sublist,list) else [])])
print(json.dumps(result))
