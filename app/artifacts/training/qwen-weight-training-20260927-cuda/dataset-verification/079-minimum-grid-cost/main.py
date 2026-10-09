import json
import sys

def solve(grid):
    if not grid:
        return None
    
    rows = len(grid)
    cols = len(grid[0])
    
    dp = [[0] * cols for _ in range(rows)]
    dp[0][0] = grid[0][0]
    
    for r in range(rows):
        for c in range(cols):
            if r == 0 and c == 0:
                continue
            top = dp[r-1][c] if r > 0 else float('inf')
            left = dp[r][c-1] if c > 0 else float('inf')
            dp[r][c] = grid[r][c] + min(top, left)
    
    return dp[rows-1][cols-1]

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            sys.exit(0)
        
        grid = json.loads(input_data)
        result = solve(grid)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)
