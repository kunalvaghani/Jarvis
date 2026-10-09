import json
import sys

def solve_knapsack(items, capacity):
    if not items or capacity < 0:
        return 0
    
    n = len(items)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    
    for i in range(1, n + 1):
        weight, value = items[i - 1]
        for w in range(capacity + 1):
            dp[i][w] = dp[i - 1][w]
            if weight <= w:
                dp[i][w] = max(dp[i][w], dp[i - 1][w - weight] + value)
    
    return dp[n][capacity]

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(0))
            return
        
        data = json.loads(input_data)
        items, capacity = data[0], data[1]
        
        result = solve_knapsack(items, capacity)
        print(json.dumps(result))
    except Exception:
        try:
            input_data = sys.stdin.read().strip()
            if not input_data:
                print(json.dumps(0))
            else:
                data = json.loads(input_data)
                items, capacity = data[0], data[1]
                result = solve_knapsack(items, capacity)
                print(json.dumps(result))
        except Exception:
            pass

if __name__ == "__main__":
    main()
