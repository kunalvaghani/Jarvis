import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps([]), file=sys.stderr)
            return
        
        list1, list2 = input_data
        
        # Convert lists to sets for efficient intersection
        set1 = set(list1)
        set2 = set(list2)
        
        # Find the intersection of the two sets
        intersection = set1.intersection(set2)
        
        # If there is no intersection, return an empty list
        if not intersection:
            print(json.dumps([]), file=sys.stderr)
            return
        
        # Sort the intersection in descending order by frequency
        sorted_intersection = sorted(intersection.items(), key=lambda x: (-x[1], x[0]))
        
        # Collect the top k elements (minimum multiplicities)
        result = []
        for _ in range(len(sorted_intersection)):
            result.append(sorted_intersection.pop(0)[0])
        
        # Print the result as a list
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()