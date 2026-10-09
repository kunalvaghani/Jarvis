import sys
import heapq
import itertools

def merge_sorted_lists(lists):
    # Sort each list and then merge them
    sorted_lists = [sorted(lst) for lst in lists]
    merged_list = []
    while sorted_lists:
        smallest = heapq.nsmallest(1, sorted_lists)
        merged_list.append(smallest[0])
        sorted_lists.remove(smallest)
    return merged_list

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list):
            print(json.dumps([]))
            return
        
        result = merge_sorted_lists(data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()