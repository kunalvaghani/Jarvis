import sys
import json
import re


x = json.load(sys.stdin)
result = (re.sub(r"[^a-z0-9]+","-",x.lower()).strip("-"))
print(json.dumps(result))
