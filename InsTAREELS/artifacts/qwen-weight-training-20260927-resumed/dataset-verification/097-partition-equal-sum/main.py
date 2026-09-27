import json
import sys

def can_partition(nums):
    if not nums:
        return True
    total = sum(nums)
    if total % 2 != 0:
        return False
    target = total // 2
    dp = [False] * (target + 1)
    dp[0] = True
    for num in nums:
        new_dp = dp[:]
        for i in range(target, num - 1, -1):
            if dp[i - num]:
                new_dp[i] = True
        dp = new_dp
    return dp[target]

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(True))
            return
        nums = json.loads(input_data)
        if not isinstance(nums, list):
            print(json.dumps(False))
            return
        result = can_partition(nums)
        print(json.dumps(result))
    except Exception:
        print(json.dumps(False))

if __name__ == "__main__":
    main()