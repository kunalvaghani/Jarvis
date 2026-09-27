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

def business(x):
    start,end=map(date.fromisoformat,x);count=0
    while start<end:
        count+=start.weekday()<5;start+=timedelta(days=1)
    return count

x = json.load(sys.stdin)
result = (business(x))
print(json.dumps(result))
