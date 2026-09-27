import json

def main():
    # Read input from stdin
    input_data = sys.stdin.read()
    
    # Parse the input data into a list of words
    words = input_data.split()
    
    # Count occurrences of each word
    word_count = {}
    for word in words:
        if word in word_count:
            word_count[word] += 1
        else:
            word_count[word] = 1
    
    # Sort words by count in descending order, then alphabetically
    sorted_words = sorted(word_count.items(), key=lambda x: (-x[1], x[0]))
    
    # Format the output as requested
    formatted_output = []
    for word, count in sorted_words:
        formatted_output.append({"input": [word], "expected": [[word, count]]})
    
    # Write the formatted output to stdout
    print(json.dumps(formatted_output, indent=4))

if __name__ == "__main__":
    main()
