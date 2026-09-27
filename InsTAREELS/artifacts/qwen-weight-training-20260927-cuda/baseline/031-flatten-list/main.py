import json

def main():
    # Read input from stdin
    input_data = sys.stdin.read()
    
    # Parse the JSON input
    data = json.loads(input_data)
    
    # Flatten the nested list
    flattened_data = flatten_list(data)
    
    # Write the flattened JSON output to stdout
    print(json.dumps(flattened_data))

def flatten_list(data):
    # Base case: if the data is a list, return it as is
    if isinstance(data, list):
        return data
    
    # Recursive case: flatten each element in the list
    result = []
    for item in data:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    
    return result

if __name__ == "__main__":
    main()
