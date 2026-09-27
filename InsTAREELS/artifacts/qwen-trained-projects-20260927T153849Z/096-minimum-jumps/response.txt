import sys
import json

def jump_game(x):
    n = len(x)
    if n == 0:
        return 0
    if n == 1:
        return 0
    if x[0] == -1:
        return -1
    if x[n-1] == -1:
        return -1
    
    dp = [float('inf')] * n
    dp[0] = 0
    for i in range(1,n):
        for j in range(i):
            if x[j] != -1 and dp[j] != float('inf'):
                dp[i] = min(dp[i],dp[j]+1)
    
    return dp[-1]

x = json.load(sys.stdin)
result = (jump_game(x))
print(json.dumps(result))
