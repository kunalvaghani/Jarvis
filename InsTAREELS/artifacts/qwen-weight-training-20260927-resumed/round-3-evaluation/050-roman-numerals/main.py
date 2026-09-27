import sys
import json


x = json.load(sys.stdin)
result = (''.join(['XCIX' if i<=x else 'XC' if i<=400 else 'LX' if i<=900 else 'XC' if i<=4000 else 'CD' if i<=9000 else 'D' for i in x]))
print(json.dumps(result))
