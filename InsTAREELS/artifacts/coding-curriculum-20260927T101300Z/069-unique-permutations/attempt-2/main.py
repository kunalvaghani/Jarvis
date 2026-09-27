import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(1)

    if not isinstance(input_data, list):
        sys.exit(1)

    # Handle empty list case
    if len(input_data) == 0:
        print(json.dumps([]))
        return

    # Get unique elements sorted
    unique_elements = sorted(set(input_data))
    
    # Generate all permutations using backtracking
    result = []
    
    def backtrack(path, remaining):
        if len(remaining) == 0:
            result.append(path[:])
            return
        
        for i in range(len(unique_elements)):
            val = unique_elements[i]
            # Create a new list with one less element at index i
            new_remaining = remaining[:i] + remaining[i+1:]
            backtrack(path + [val], new_remaining)
    
    backtrack([], list(unique_elements))
    
    # Sort the result for consistent output
    result.sort()
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()