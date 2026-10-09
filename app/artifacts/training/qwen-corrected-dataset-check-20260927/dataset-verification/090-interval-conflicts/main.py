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
result = ([[i,j] for i,a in enumerate(x) for j,b in enumerate(x) if i<j and max(a[0],b[0])<=min(a[1],b[1])])
print(json.dumps(result))
