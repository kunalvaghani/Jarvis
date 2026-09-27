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
result = (sorted({tuple(sorted(t)) for t in itertools.combinations(x,3) if sum(t)==0}))
print(json.dumps(result))
