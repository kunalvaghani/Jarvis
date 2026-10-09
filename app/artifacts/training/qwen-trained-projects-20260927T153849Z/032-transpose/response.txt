import sys
import json


def transpose(matrix):
    if not matrix:
        return []
    result = []
    for i in range(len(matrix[0])):
        row = []
        for j in range(len(matrix)):
            row.append(matrix[j][i])
        result.append(row)
    return result


x = json.load(sys.stdin)
result = transpose(x)
print(json.dumps(result))
