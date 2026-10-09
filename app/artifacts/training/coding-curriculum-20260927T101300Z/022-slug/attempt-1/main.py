import json
import sys

def slugify(text):
    text = text.lower()
    result = []
    prev_is_alpha = False
    for char in text:
        is_alpha = char.isalpha() or char.isdigit()
        if not is_alpha:
            if prev_is_alpha:
                result.append('-')
            result.append(char)
            prev_is_alpha = False
        else:
            if prev_is_alpha and not is_alpha:
                pass
            elif not prev_is_alpha and is_alpha:
                result.append(char)
            prev_is_alpha = True
    return ''.join(result).strip('-')

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            json.dump(None, sys.stdout)
            return
        parsed = json.loads(input_data)
        result = slugify(str(parsed))
        json.dump(result, sys.stdout)
    except (json.JSONDecodeError, ValueError):
        json.dump(None, sys.stdout)

if __name__ == "__main__":
    main()