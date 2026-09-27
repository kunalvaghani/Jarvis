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
result = ([p for p in range(2,x+1) if all(p%d for d in range(2,math.isqrt(p)+1))])
print(json.dumps(result))
