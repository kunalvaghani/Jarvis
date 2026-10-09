import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        matrix_a = input_data[0]
        matrix_b = input_data[1]
        
        if not (isinstance(matrix_a, list) and isinstance(matrix_b, list)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if len(matrix_a) == 0 or len(matrix_b) == 0:
            print(json.dumps(None), file=sys.stderr)
            return
        
        rows_a = len(matrix_a)
        cols_a = len(matrix_a[0])
        rows_b = len(matrix_b)
        cols_b = len(matrix_b[0])
        
        if not (all(len(row) == cols_a for row in matrix_a)) or not (all(len(row) == cols_b for row in matrix_b)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if cols_a != rows_b:
            print(json.dumps(None), file=sys.stderr)
            return
        
        result = []
        for i in range(rows_a):
            row = []
            for j in range(cols_b):
                val = 0
                for k in range(cols_a):
                    val += matrix_a[i][k] * matrix_b[k][j]
                row.append(val)
            result.append(row)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()