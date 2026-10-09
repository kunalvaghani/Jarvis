import sys

def transpose_matrix(matrix):
    if not matrix:
        return []
    
    transposed = []
    for i in range(len(matrix[0])):
        transposed.append([matrix[j][i] for j in range(len(matrix))]
    return transposed

def main():
    input_data = sys.stdin.read()
    try:
        data = json.loads(input_data)
        result = transpose_matrix(data['input'])
        print(json.dumps(result))
    except json.JSONDecodeError:
        print("Invalid JSON input")

if __name__ == "__main__":
    main()
