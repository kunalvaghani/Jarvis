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
result = (re.sub(r"[^a-z0-9]+","-",x.lower()).strip("-"))
print(json.dumps(result))
