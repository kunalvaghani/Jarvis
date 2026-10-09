import json

def main():
    # Read input from stdin
    input_data = sys.stdin.read()
    
    # Parse the JSON input
    data = json.loads(input_data)
    
    # Extract the list and positive window size from the input
    list_value = data['input'][0]
    window_size = data['input'][1]
    
    # Initialize an empty list to store the result
    result = []
    
    # Iterate over the list with a sliding window
    for i in range(len(list_value) - window_size + 1):
        # Calculate the current window
        window = list_value[i:i+window_size]
        
        # Calculate the mean of the window
        mean = sum(window) / window_size
        
        # Append the mean to the result list
        result.append(mean)
    
    # Write the result to stdout
    print(json.dumps(result))

if __name__ == "__main__":
    main()
