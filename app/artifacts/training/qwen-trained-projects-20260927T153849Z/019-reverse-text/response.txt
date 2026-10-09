import sys
import json

x = json.load(sys.stdin)
result = (json.dumps((x[::-1])))
print(result)
