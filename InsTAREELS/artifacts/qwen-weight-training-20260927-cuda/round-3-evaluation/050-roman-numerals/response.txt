import json
import sys

def int_to_roman(num):
    if num < 1 or num > 3999:
        raise ValueError("Input must be between 1 and 3999")
    
    roman_numerals = [
        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'),
        (1, 'I')
    ]
    
    result = ''
    for value, numeral in roman_numerals:
        while num >= value:
            result += numeral
            num -= value
    return result

try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
    sys.exit(1)

if not isinstance(input_data, int) or input_data < 1 or input_data > 3999:
    print(json.dumps({"error": "Input must be between 1 and 3999"}), file=sys.stderr)
    sys.exit(1)

result = int_to_roman(input_data)
print(result)