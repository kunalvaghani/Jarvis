import sys
import itertools
import operator


def solve(n):
    if n<0:
        return []
    if n==0:
        return [""]
    res=[]
    for i in range(1,n+1):
        for subset in itertools.combinations(range(i),2):
            res.append("".join(sorted(subset)))
    return sorted(set(res))


x = json.load(sys.stdin)
result = (solve(x))
print(json.dumps(result))
