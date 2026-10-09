import sys
import csv
import io
import json


x = json.load(sys.stdin)
result = (list(csv.DictReader(io.StringIO(x))))
print(json.dumps(result))
