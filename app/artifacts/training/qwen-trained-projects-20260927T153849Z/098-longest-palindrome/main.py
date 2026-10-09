import sys
import bisect
import itertools

def longest_palindrome(s):
    n = len(s)
    if n == 0:
        return ""
    
    def is_palindrome(sub):
        return sub == sub[::-1]
    
    def expand_around_center(left, right):
        while left >= 0 and right < n and s[left] == s[right]:
            left -= 1
            right += 1
        return (left + 1, right - 1)
    
    max_length = 0
    best_start = 0
    
    for i in range(n):
        # Odd-length palindromes
        odd_len = expand_around_center(i, i)
        max_length = max(max_length, odd_len[1] - odd_len[0] + 1)
        best_start = odd_len[0]
        
        # Even-length palindromes
        even_len = expand_around_center(i, i + 1)
        max_length = max(max_length, even_len[1] - even_len[0] + 1)
        best_start = max(best_start, even_len[0])
    
    return s[best_start:best_start + max_length]

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(""))
            return
        
        result = longest_palindrome(input_data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()