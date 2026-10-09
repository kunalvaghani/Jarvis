import sys
import bisect
import heapq

def median(nums):
    n = len(nums)
    if n == 0:
        return None
    if n % 2 == 1:
        return nums[n // 2]
    else:
        mid1 = nums[n // 2 - 1]
        mid2 = nums[n // 2]
        return (mid1 + mid2) / 2.0

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        x = json.loads(input_data)
        
        result = median(x)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()