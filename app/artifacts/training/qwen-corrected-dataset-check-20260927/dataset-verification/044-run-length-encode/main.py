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

def rle(s):
    return [[k,len(list(v))] for k,v in itertools.groupby(s)]

x = json.load(sys.stdin)
result = (rle(x))
print(json.dumps(result))
