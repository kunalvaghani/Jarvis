import sys
import json


x = json.load(sys.stdin)
result = (max(set(x)) if len(set(x))<2 else None)
print(json.dumps(result))
