import json

def main():
    # Read input from stdin
    input_data = sys.stdin.read()
    
    # Parse the input data into a list of strings
    input_list = input_data.split(',')
    
    # Convert each string to a datetime object
    input_dates = [datetime.strptime(date, '%Y-%m-%d') for date in input_list]
    
    # Find the maximum and minimum dates
    max_date = max(input_dates)
    min_date = min(input_dates)
    
    # Calculate the difference between the maximum and minimum dates
    delta = max_date - min_date
    
    # Format the result as a JSON object
    result = {
        "input": input_list,
        "expected": delta.days
    }
    
    # Write the result to stdout
    print(json.dumps(result, indent=4))

if __name__ == "__main__":
    main()
