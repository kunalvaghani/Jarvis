import json
import sys

def longest_palindrome(s: str) -> str:
    if not s:
        return ""
    n = len(s)
    max_len = 0
    start_idx = 0
    
    for i in range(n):
        # Check odd length palindromes
        left, right = i, i
        while left >= 0 and right < n and s[left] == s[right]:
            if (right - left + 1) > max_len:
                max_len = right - left + 1
                start_idx = left
            left -= 1
            right += 1
        
        # Check even length palindromes
        left, right = i, i + 1
        while left >= 0 and right < n and s[left] == s[right]:
            if (right - left + 1) > max_len:
                max_len = right - left + 1
                start_idx = left
            left -= 1
            right += 1
    
    return s[start_idx:start_idx + max_len]

if __name__ == "__main__":
    input_data = sys.stdin.read().strip()
    if not input_data:
        print(json.dumps(""))
    else:
        try:
            parsed = json.loads(input_data)
            if isinstance(parsed, str):
                result = longest_palindrome(parsed)
                print(json.dumps(result))
            else:
                print(json.dumps(""))
        except json.JSONDecodeError:
            print(json.dumps(""))