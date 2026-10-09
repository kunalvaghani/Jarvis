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

def dijkstra(x):
    graph,start=x;cost={start:0};queue=[(0,start)]
    while queue:
        d,node=heapq.heappop(queue)
        if d!=cost[node]:continue
        for neighbor,weight in graph.get(node,[]):
            candidate=d+weight
            if candidate<cost.get(neighbor,math.inf):cost[neighbor]=candidate;heapq.heappush(queue,(candidate,neighbor))
    return dict(sorted(cost.items()))

x = json.load(sys.stdin)
result = (dijkstra(x))
print(json.dumps(result))
