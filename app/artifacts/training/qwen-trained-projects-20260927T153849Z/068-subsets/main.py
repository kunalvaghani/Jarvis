import sys
import itertools
import json

def distinct_subsets(x):
    if not x:
        return [[]]
    result = []
    for i in range(len(x)+1):
        for subset in distinct_subsets(x[:i]):
            result.append(subset+[x[i]])
    return sorted(result)

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(None), file=sys.stderr)
        return
    
    if not isinstance(input_data, list) or len(input_data) != 1:
        print(json.dumps(None), file=sys.stderr)
        return
    
    result = distinct_subsets(input_data[0])
    print(json.dumps(result))

if __name__ == "__main__":
    main()