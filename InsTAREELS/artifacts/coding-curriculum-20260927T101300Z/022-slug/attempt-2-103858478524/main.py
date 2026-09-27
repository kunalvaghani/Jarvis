import json
import sys

def slugify(text):
    text = text.lower()
    result = []
    prev_is_alpha = True
    for char in text:
        if char.isalnum():
            prev_is_alpha = True
            result.append(char)
        else:
            if not prev_is_alpha or (len(result) > 0 and result[-1] != '-'):
                result.append('-')
            prev_is_alpha = False
    return ''.join(result).strip('-')

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.stderr.write('Invalid JSON\n')
        sys.exit(1)
    
    if isinstance(data, list):
        result = [slugify(item) for item in data]
    else:
        result = slugify(data)
    
    print(json.dumps(result))

if __name__ == '__main__':
    main()