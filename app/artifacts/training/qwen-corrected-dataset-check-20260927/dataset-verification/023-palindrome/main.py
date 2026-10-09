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
result = ((lambda s:s==s[::-1])("".join(c.lower() for c in x if c.isalnum())))
print(json.dumps(result))
