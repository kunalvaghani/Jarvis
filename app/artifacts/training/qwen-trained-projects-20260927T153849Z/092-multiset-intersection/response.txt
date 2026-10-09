import sys
import itertools

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps([]), file=sys.stderr)
            return
        
        x, y = data
        
        if not (isinstance(x, list) and isinstance(y, list)):
            print(json.dumps([]), file=sys.stderr)
            return
        
        if len(x) == 0 or len(y) == 0:
            print(json.dumps([]), file=sys.stderr)
            return
        
        result = []
        
        for i in range(len(x)):
            for j in range(len(y)):
                if x[i] == y[j]:
                    result.append(x[i])
                    break
        
        result.sort()
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()