import sys
import re


x = json.load(sys.stdin)
result = (len(re.findall(r'\b\w+\b', x)))
print(json.dumps(result))
