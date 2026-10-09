import sys
import json

def rotate_right(lst, k):
    if not lst:
        return []
    n = len(lst)
    k = k % n
    if k == 0:
        return lst
    return lst[-k:] + lst[:-k]

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        result = rotate_right(data[0], data[1])
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()