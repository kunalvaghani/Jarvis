import sys
import itertools

def lcs(x, y):
    m, n = len(x), len(y)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if x[i - 1] == y[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        x = json.loads(input_data)
        if not isinstance(x, list) or len(x) != 2:
            print(json.dumps(None))
            return
        
        result = lcs(*x)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None))

if __name__ == "__main__":
    main()