import sys

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32

def main():
    # Read input from sys.stdin
    input_value = sys.stdin.read()
    
    # Convert the input value to a float
    try:
        celsius = float(input_value)
    except ValueError:
        print("Invalid input. Please enter a valid number.")
        return
    
    # Convert Celsius to Fahrenheit
    fahrenheit = celsius_to_fahrenheit(celsius)
    
    # Write the result to stdout
    print(f"{fahrenheit:.2f}")

if __name__ == "__main__":
    main()
