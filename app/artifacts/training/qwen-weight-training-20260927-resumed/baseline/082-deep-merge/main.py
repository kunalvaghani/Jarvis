import json

def merge_jsons(input_data):
    # Base case: if the input is empty, return an empty dictionary
    if not input_data:
        return {}
    
    # Recursive case: merge the first element with the result of the recursive call on the rest of the input
    merged = input_data[0]
    for item in input_data[1:]:
        merged.update(item)
    
    return merged

# Read input from stdin
input_value = sys.stdin.read()

# Merge the JSON values
merged_output = merge_jsons(json.loads(input_value))

# Write the merged JSON output to stdout
print(merged_output)
