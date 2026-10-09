import sys
import bisect
import json

def lis(values):
    tail=[]
    for value in values:
        i=bisect.bisect_left(tail,value)
        if i==len(tail):tail.append(value)
        else:tail[i]=value
    return len(tail)

x = json.load(sys.stdin)
result = (lis(x))
print(json.dumps(result))
