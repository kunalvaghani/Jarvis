import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(data, list):
        return
    
    result = []
    for i in range(len(data) + 1):
        subset = []
        for j in range(i):
            subset.append(data[j])
        subset.sort()
        result.append(subset)
    
    result.sort()
    print(json.dumps(result))

if __name__ == "__main__":
    main()