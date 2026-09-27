import sys
import json


x = json.load(sys.stdin)
result = (sorted((sorted(c.split(),key=lambda w:w.lower()),reverse=True),key=lambda c:(c[1],c[0])),key=lambda c:(c[1],c[0])))
print(json.dumps(result))
