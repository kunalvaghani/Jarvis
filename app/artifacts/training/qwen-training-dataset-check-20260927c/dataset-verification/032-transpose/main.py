import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        return
    
    if not isinstance(input_data, list):
        print(json.dumps(None), file=sys.stderr)
        return
    
    if len(input_data) == 0:
        print(json.dumps([]))
        return
    
    transposed = []
    for i in range(len(input_data[0])):
        row = []
        for row_data in input_data:
            if isinstance(row_data, list):
                row.append(row_data[i])
            else:
                print(json.dumps(None), file=sys.stderr)
                return
        transposed.append(row)
    
    print(json.dumps(transposed))

if __name__ == "__main__":
    main()