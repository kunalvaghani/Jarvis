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

def cache(x):
    capacity,keys=x;order=[];hits=0
    for key in keys:
        if key in order:hits+=1;order.remove(key)
        order.append(key)
        if len(order)>capacity:order.pop(0)
    return {'hits':hits,'keys':order}

x = json.load(sys.stdin)
result = (cache(x))
print(json.dumps(result))
