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


x = json.load(sys.stdin)
result = (sorted([sorted(c) for n in range(len(x)+1) for c in itertools.combinations(x,n)]))
print(json.dumps(result))
