import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps(-1))
            return
        
        denominations = [int(x) for x in data[0]]
        target = int(data[1])
        
        if any(d <= 0 for d in denominations):
            print(json.dumps(-1))
            return
        
        if target < 0:
            print(json.dumps(-1))
            return
        
        dp = [float('inf')] * (target + 1)
        dp[0] = 0
        
        for d in denominations:
            for i in range(d, target + 1):
                if dp[i - d] != float('inf'):
                    dp[i] = min(dp[i], dp[i - d] + 1)
        
        result = int(dp[target]) if dp[target] != float('inf') else -1
        print(json.dumps(result))
    except Exception:
        print(json.dumps(-1))

if __name__ == "__main__":
    main()