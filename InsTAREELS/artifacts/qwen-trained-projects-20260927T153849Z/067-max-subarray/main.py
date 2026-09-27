import sys
import itertools
import numpy as np

def max_subarray_sum(arr):
    if not arr:
        return 0
    
    current_max = max_so_far = arr[0]
    for num in arr[1:]:
        current_max = max(num, current_max + num)
        max_so_far = max(max_so_far, current_max)
    return max_so_far

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        result = max_subarray_sum(eval(input_data))
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()