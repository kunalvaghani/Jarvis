import sys
import re
import string

def count_vowels(s):
    return sum(1 for c in s.lower() if c in string.ascii_lowercase and c in 'aeiou')

x = json.load(sys.stdin)
result = (count_vowels(x))
print(json.dumps(result))
