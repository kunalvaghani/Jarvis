import sys
import json


def jaccard_similarity(list1, list2):
    if not list1 or not list2:
        return 1
    set1 = set(list1)
    set2 = set(list2)
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union)


x = json.load(sys.stdin)
result = (jaccard_similarity(x[0], x[1]))
print(json.dumps(result))
