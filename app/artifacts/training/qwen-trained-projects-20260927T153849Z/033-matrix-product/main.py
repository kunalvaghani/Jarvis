import sys
import numpy as np

def matrix_multiply(A, B):
    return np.dot(A, B)

x = json.load(sys.stdin)
result = matrix_multiply(x[0], x[1])
print(json.dumps(result))
