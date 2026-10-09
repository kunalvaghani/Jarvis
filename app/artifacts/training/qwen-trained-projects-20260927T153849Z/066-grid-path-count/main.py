import sys
import json

def count_right_down_paths(grid):
    rows, cols = len(grid), len(grid[0])
    dp = [[0] * (cols + 1) for _ in range(rows + 1)]
    
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            if grid[i - 1][j - 1] == 1:
                dp[i][j] = dp[i - 1][j] + dp[i][j - 1]
            else:
                dp[i][j] = dp[i - 1][j] + dp[i][j - 1]
    
    return dp[-1][-1]

try:
    input_data = sys.stdin.read().strip()
    result = count_right_down_paths(json.loads(input_data))
    print(json.dumps(result))
except (json.JSONDecodeError, ValueError):
    pass