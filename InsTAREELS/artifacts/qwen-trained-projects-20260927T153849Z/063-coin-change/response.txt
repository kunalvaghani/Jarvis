import sys
import itertools
import bisect

def solve(coins, target):
    if target < 0:
        return -1
    if not coins:
        return 0
    dp = [float('inf')] * (target + 1)
    dp[0] = 0
    for coin in coins:
        for i in range(coin, target + 1):
            dp[i] = min(dp[i], dp[i - coin] + 1)
    return dp[target] if dp[target] != float('inf') else -1

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps(None))
            return
        
        coins = data[0]
        target = data[1]
        
        result = solve(coins, target)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()