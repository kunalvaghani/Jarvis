import sys
import itertools
import json

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if len(data) != 2:
            print(json.dumps([]))
            return
        
        list1, list2 = data[0], data[1]
        
        if not (isinstance(list1, list) and isinstance(list2, list)):
            print(json.dumps([]))
            return
        
        if len(list1) == 0 or len(list2) == 0:
            print(json.dumps([]))
            return
        
        # Use set intersection to find common elements
        intersection = set(list1).intersection(set(list2))
        
        # Sort the intersection by frequency and then by element
        sorted_intersection = sorted(intersection.items(), key=lambda x: (-x[1], x[0]))
        
        # Collect the result into a list
        result = [item[0] for item in sorted_intersection]
        
        # Print the result as a JSON string
        print(json.dumps(result))

if __name__ == "__main__":
    main()