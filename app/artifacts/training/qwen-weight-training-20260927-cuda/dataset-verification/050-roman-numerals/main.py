import json
import sys

def roman_value(n):
    """
    Convert an integer (1..3999) to its uppercase Roman numeral representation.
    
    Args:
        n: Integer between 1 and 3999 inclusive.
    
    Returns:
        Uppercase Roman numeral string.
    """
    if not (1 <= n <= 3999):
        raise ValueError("Input must be an integer between 1 and 3999.")
    
    values = [
        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')
    ]
    
    result = []
    for value, numeral in values:
        while n >= value:
            result.append(numeral)
            n -= value
    
    return ''.join(result)

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, int):
            raise ValueError("Input must be an integer.")
        output = roman_value(input_data)
        print(json.dumps(output))
    except (json.JSONDecodeError, ValueError) as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
