import json
import sys

def is_palindrome(s):
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]

def main():
    try:
        data = json.load(sys.stdin)
        result = is_palindrome(data)
        print(result)
    except Exception as e:
        sys.stderr.write(str(e) + '\n')

if __name__ == '__main__':
    main()
