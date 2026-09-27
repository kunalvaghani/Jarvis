import sys
from datetime import date, timedelta
import json

def business(x):
    start,end=map(date.fromisoformat,x);count=0
    while start<end:
        count+=start.weekday()<5;start+=timedelta(days=1)
    return count

x = json.load(sys.stdin)
result = (business(x))
print(json.dumps(result))
