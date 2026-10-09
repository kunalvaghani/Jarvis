import json

def main():
    # Read input from stdin
    input_data = sys.stdin.read()
    
    # Parse the JSON input
    data = json.loads(input_data)
    
    # Initialize the result with 1 (empty product)
    result = 1
    
    # Iterate over each item in the input data
    for item in data['input']:
        # Multiply the current item by the result
        result *= item
    
    # Write the result to stdout
    print(json.dumps(result))

if __name__ == "__main__":
    main()
