import json

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
            raise ValueError(f"Invalid character: {char}")
    return total

def int_to_roman(n):
    if n < 1 or n > 3999:
        raise ValueError("Number out of range")
    roman_map = [
        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')
    ]
    roman = ''
    for value, symbol in roman_map:
        while n >= value:
            roman += symbol
            n -= value
    return roman

if __name__ == "__main__":
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, dict) or not input_data.get('input'):
            raise ValueError("Input must be a dictionary with an 'input' key.")
        if not isinstance(input_data['input'], int) or input_data['input'] < 1 or input_data['input'] > 3999:
            raise ValueError("Input must be an integer between 1 and 3999.")
        result = int_to_roman(input_data['input'])
        print(result)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}))
    except ValueError as e:
        print(json.dumps({"error": str(e)}))