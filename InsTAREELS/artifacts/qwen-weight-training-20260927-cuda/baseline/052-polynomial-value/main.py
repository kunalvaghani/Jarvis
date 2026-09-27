import json

def main():
    # Read input from stdin
    input_data = json.load(sys.stdin)
    
    # Extract the input data
    input_value = input_data['input']
    
    # Calculate the ascending-power coefficients
    ascending_power_coefficients = [1] * len(input_value[0])
    for i in range(1, len(input_value[0])):
        ascending_power_coefficients[i] = ascending_power_coefficients[i-1] * input_value[0][i]
    
    # Evaluate the polynomial
    result = 0
    for coeff, power in zip(ascending_power_coefficients, input_value[0]):
        result += coeff * (10 ** power)
    
    # Write the result to stdout
    print(json.dumps({'expected': result}))

if __name__ == "__main__":
    main()
