import sys
import bisect
import itertools
import operator

def intersect(a,b):
    return [x for x in a if x in b]

def main():
    try:
        data = sys.stdin.read().strip()
        if not data:
            print(json.dumps([]))
            return
        
        x = json.loads(data)
        
        if not isinstance(x,list) or len(x)<2:
            print(json.dumps([]))
            return
        
        y = x[1]
        
        if not isinstance(y,list) or len(y)<2:
            print(json.dumps([]))
            return
        
        result = []
        
        for a in x[0]:
            for b in y:
                result.append(intersect(a,b))
        
        result = list(set(result))
        result.sort()
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]),file=sys.stderr)

if __name__ == "__main__":
    main()