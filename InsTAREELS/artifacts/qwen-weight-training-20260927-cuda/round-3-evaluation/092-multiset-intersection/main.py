import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps([]), file=sys.stderr)
            return
        
        list1, list2 = input_data
        
        if not isinstance(list1, list) or not isinstance(list2, list):
            print(json.dumps([]), file=sys.stderr)
            return
        
        if len(list1) == 0 or len(list2) == 0:
            print(json.dumps([]), file=sys.stderr)
            return
        
        result = []
        
        for num in list1:
            if num in list2:
                result.append(num)
        
        result.sort()
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()