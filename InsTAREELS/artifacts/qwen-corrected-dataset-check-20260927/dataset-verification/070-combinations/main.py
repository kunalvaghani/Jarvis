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
result = (sorted({tuple(sorted(c)) for c in itertools.combinations(x[0],x[1])}))
print(json.dumps(result))
