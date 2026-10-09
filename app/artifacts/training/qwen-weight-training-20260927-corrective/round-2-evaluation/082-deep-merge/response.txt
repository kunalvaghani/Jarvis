import sys
import json


x = json.load(sys.stdin)
result = (lambda x,y:(x if isinstance(x,list) and isinstance(y,list) else (x if isinstance(x,dict) and isinstance(y,dict) else (x if isinstance(x,set) and isinstance(y,set)) if x==y else (x if isinstance(x,int) and isinstance(y,int)) else (x,y))))
print(json.dumps(result(*x)))
