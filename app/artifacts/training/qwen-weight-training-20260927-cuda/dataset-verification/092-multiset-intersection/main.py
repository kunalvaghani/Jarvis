import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None))
            return
        
        list1 = input_data[0]
        list2 = input_data[1]
        
        if not isinstance(list1, list) or not isinstance(list2, list):
            print(json.dumps(None))
            return
        
        set1 = set()
        count1 = {}
        for item in list1:
            if isinstance(item, int):
                set1.add(item)
                count1[item] = count1.get(item, 0) + 1
            else:
                print(json.dumps(None))
                return
        
        set2 = set()
        count2 = {}
        for item in list2:
            if isinstance(item, int):
                set2.add(item)
                count2[item] = count2.get(item, 0) + 1
            else:
                print(json.dumps(None))
                return
        
        intersection_set = set1 & set2
        result = []
        for item in sorted(intersection_set):
            min_count = min(count1.get(item, 0), count2.get(item, 0))
            for _ in range(min_count):
                result.append(item)
        
        print(json.dumps(result))
    except Exception:
        print(json.dumps(None))

if __name__ == "__main__":
    main()