import sys
import json


def can_split_to_equal_subset(nums):
    n = len(nums)
    if n == 0:
        return True
    if n % 2 != 0:
        return False
    
    target = sum(nums) // 2
    dp = [[False] * (target + 1) for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        for j in range(target + 1):
            if nums[i - 1] <= j:
                dp[i][j] = dp[i - 1][j] or dp[i - 1][j - nums[i - 1]]
            else:
                dp[i][j] = dp[i - 1][j]
    
    return dp[n][target]


if __name__ == "__main__":
    import sys
    import json
    result = can_split_to_equal_subset(json.load(sys.stdin))
    print(json.dumps(result))
