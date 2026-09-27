import sys
import base64
import bisect
from collections import Counter
import csv
from datetime import date, timedelta
import hashlib
import heapq
import io
import itertools
import json
import math
import re
import statistics

def lis(values):
    tail=[]
    for value in values:
        i=bisect.bisect_left(tail,value)
        if i==len(tail):tail.append(value)
        else:tail[i]=value
    return len(tail)

x = json.load(sys.stdin)
result = (lis(x))
print(json.dumps(result))
