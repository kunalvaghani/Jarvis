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

def rpn(tokens):
    stack=[]
    for token in tokens:
        if token in ['+','-','*','/']:
            b,a=stack.pop(),stack.pop();stack.append({'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[token]())
        else:stack.append(float(token))
    return stack[0]

x = json.load(sys.stdin)
result = (rpn(x))
print(json.dumps(result))
