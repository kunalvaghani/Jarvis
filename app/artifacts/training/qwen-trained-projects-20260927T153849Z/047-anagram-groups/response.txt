import sys
import json


def group_anagrams(s):
    return [sorted(x) for x in (sorted(set(s)) for s in s.split())]


x = json.load(sys.stdin)
result = (json.dumps(group_anagrams(x)))
print(result)
