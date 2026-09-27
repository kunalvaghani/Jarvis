import json

def roman_to_int(roman):
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
    for char in roman:
        total += roman_map[char]
    return total

def int_to_roman(num):
    if num < 1 or num > 3999:
        raise ValueError("Input must be between 1 and 3999")
    
    roman_numerals = [
        "M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX",
        "V", "IV", "I"
    ]
    result = ""
    for i, value in enumerate(roman_numerals):
        while num >= value:
            result += value
            num -= value
    return result

def main():
    input_data = json.load(sys.stdin)
    output_data = []
    
    for data in input_data:
        input_value = data['input']
        expected_output = data['expected']
        
        try:
            input_value = int(input_value)
            output_value = int_to_roman(input_value)
        except ValueError as e:
            print(f"Error: {e}")
            continue
        
        output_data.append({"input": input_value, "expected": output_value})
    
    json.dump(output_data, sys.stdout, indent=4)

if __name__ == "__main__":
    main()
