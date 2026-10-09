import sys
import re

def is_palindrome(s):
    s = s.lower()
    return s == s[::-1]

x = json.load(sys.stdin)
result = (json.dumps(is_palindrome(x)))
print(result)
