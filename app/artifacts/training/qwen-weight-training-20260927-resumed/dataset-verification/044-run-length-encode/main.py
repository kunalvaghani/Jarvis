import sys
import itertools
import json

def rle(s):
    return [[k,len(list(v))] for k,v in itertools.groupby(s)]

x = json.load(sys.stdin)
result = (rle(x))
print(json.dumps(result))
