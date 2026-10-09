import sys
import json


def knapsack(weights, values, capacity):
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        for w in range(1, capacity + 1):
            if weights[i - 1][0] > w:
                dp[i][w] = dp[i - 1][w]
            else:
                dp[i][w] = max(dp[i - 1][w], dp[i - 1][w - weights[i - 1][0]] + values[i - 1][1])
    
    return dp[n][capacity]


if __name__ == "__main__":
    import sys
    import json
    
    try:
        input_data = sys.stdin.read().strip()
    except Exception:
        sys.exit(1)
    
    if not input_data:
        sys.exit(0)
    
    try:
        data = json.loads(input_data)
    except Exception:
        sys.exit(1)
    
    if not isinstance(data, list) or len(data) != 2:
        sys.exit(1)
    
    weights = data[0]
    values = data[1]
    capacity = data[2]
    
    result = knapsack(weights, values, capacity)
    print(json.dumps(result))
