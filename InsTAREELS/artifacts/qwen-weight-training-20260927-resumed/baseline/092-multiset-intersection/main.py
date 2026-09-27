import json

def main():
    # Read input from stdin
    input_data = sys.stdin.read()
    
    # Parse the JSON input
    data = json.loads(input_data)
    
    # Extract the list of lists from the input
    lists = data['input']
    
    # Find the intersection of all lists
    intersection = list(set.intersection(*lists))
    
    # Sort the intersection by length and then by elements
    sorted_intersection = sorted(intersection, key=lambda x: (-len(x), x))
    
    # Write the sorted intersection to stdout
    print(json.dumps(sorted_intersection))

if __name__ == "__main__":
    main()
