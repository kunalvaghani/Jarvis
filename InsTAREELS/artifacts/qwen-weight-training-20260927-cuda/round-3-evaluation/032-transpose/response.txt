import json
import sys

def transpose(matrix):
    if not matrix:
        return []
    
    rows = len(matrix)
    cols = len(matrix[0])
    result = [[0] * cols for _ in range(rows)]
    
    for i in range(rows):
        for j in range(cols):
            result[i][j] = matrix[j][i]
    
    return result

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps([]), file=sys.stderr)
        sys.exit(1)
    
    if not isinstance(input_data, list) or len(input_data) == 0:
        print(json.dumps([]), file=sys.stderr)
        sys.exit(1)
    
    result = transpose(input_data)
    print(json.dumps(result))

if __name__ == "__main__":
    main()