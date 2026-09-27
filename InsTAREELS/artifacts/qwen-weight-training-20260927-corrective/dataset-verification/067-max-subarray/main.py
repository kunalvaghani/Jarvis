import sys
import json

def maxsum(values):
    best=current=values[0]
    for value in values[1:]:current=max(value,current+value);best=max(best,current)
    return best

x = json.load(sys.stdin)
result = (maxsum(x))
print(json.dumps(result))
