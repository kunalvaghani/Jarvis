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

def maxsum(values):
    best=current=values[0]
    for value in values[1:]:current=max(value,current+value);best=max(best,current)
    return best

x = json.load(sys.stdin)
result = (maxsum(x))
print(json.dumps(result))
