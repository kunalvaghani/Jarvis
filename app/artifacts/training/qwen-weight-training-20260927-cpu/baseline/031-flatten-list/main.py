import json

def flatten_json(input_data):
    # Flatten the nested list
    flattened = []
    for item in input_data:
        if isinstance(item, list):
            flattened.extend(flatten_json(item))
        else:
            flattened.append(item)
    return flattened

# Read input from stdin
input_data = json.load(sys.stdin)

# Flatten the input data
flattened_data = flatten_json(input_data)

# Write the flattened data to stdout
json.dump(flattened_data, sys.stdout, indent=4)
