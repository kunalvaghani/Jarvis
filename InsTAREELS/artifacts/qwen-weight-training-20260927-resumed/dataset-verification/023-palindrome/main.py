import sys
import json


x = json.load(sys.stdin)
result = ((lambda s:s==s[::-1])("".join(c.lower() for c in x if c.isalnum())))
print(json.dumps(result))
