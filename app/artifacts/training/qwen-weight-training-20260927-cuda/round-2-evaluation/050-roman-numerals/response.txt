import json
import sys

def roman_to_int(s):
    roman_map = {
        'I': 1,
        'V': 5,
        'X': 10,
        'L': 50,
        'C': 100,
        'D': 500,
        'M': 1000
    }
    total = 0
    for char in s:
        if char in roman_map:
            total += roman_map[char]
        else:
            return None
    return total

def int_to_roman(num):
    if num < 1 or num > 3999:
        return None
    result = []
    for value, symbol in sorted(roman_map.items(), reverse=True):
        while num >= value:
            result.append(symbol)
            num -= value
    return ''.join(result)

if __name__ == "__main__":
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, dict) or 'input' not in input_data:
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        
        input_value = input_data.get('input')
        if not isinstance(input_value, (int, float)):
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        
        if not (isinstance(input_value, int) and 1 <= input_value <= 3999):
            print(json.dumps(None), file=sys.stderr)
            sys.exit(1)
        
        result = int_to_roman(input_value)
        if result is None:
            print(json.dumps(None), file=sys.stderr)
        else:
            print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)