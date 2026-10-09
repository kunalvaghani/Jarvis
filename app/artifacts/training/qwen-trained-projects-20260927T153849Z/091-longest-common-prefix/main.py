import sys
import json

def longest_common_prefix(strs):
    if not strs:
        return ""
    
    prefix = strs[0]
    for s in strs[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix

x = json.load(sys.stdin)
result = longest_common_prefix(x)
print(json.dumps(result))
