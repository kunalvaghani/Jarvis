import sys
import json
import statistics


x = json.load(sys.stdin)
result = (statistics.mean(x))
print(json.dumps(result))
