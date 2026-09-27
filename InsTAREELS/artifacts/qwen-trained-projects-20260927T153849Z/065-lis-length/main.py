import sys
import bisect
import itertools

def lis_length(arr):
    if not arr:
        return 0
    dp = [1] * len(arr)
    for i in range(1, len(arr)):
        for j in range(i):
            if arr[i] > arr[j]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(0))
            return
        
        x = json.loads(input_data)
        result = (lis_length(x))
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(0))

if __name__ == "__main__":
    main()