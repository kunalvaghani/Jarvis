import sys
import json

x = json.load(sys.stdin)
result = (json.dumps({k: v for k, v in collections.Counter(x).items()}))
print(result)
