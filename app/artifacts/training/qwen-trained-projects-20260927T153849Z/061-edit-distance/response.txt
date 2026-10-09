import sys
import json

def levenshtein_distance(s1, s2):
    if not s1 or not s2:
        return len(s1) + len(s2)
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]) + 1
    return dp[m][n]

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
        
        s1, s2 = data[0], data[1]
        
        result = levenshtein_distance(s1, s2)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None))

if __name__ == "__main__":
    main()