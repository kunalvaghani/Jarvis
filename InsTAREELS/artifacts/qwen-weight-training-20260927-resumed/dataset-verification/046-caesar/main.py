import json
import sys

def shift_char(c, shift):
    if 'a' <= c <= 'z':
        return chr((ord(c) - ord('a') + shift) % 26 + ord('a'))
    return c

def main():
    try:
        data = json.load(sys.stdin)
        if isinstance(data, list) and len(data) == 2:
            text, shift = data
            result = ''.join(shift_char(c, shift) for c in text)
            print(json.dumps(result))
    except Exception as e:
        sys.stderr.write(str(e) + '\n')

if __name__ == '__main__':
    main()