import json
import sys

def generate_balanced_parentheses(n):
    """
    Generate all balanced n-pair parentheses strings in lexicographic order.
    Uses a recursive backtracking approach that builds strings character by character, ensuring balance at each step.
    Lexicographic order is naturally achieved by trying '(' before ')' when appending to the current string.
    """
    results = []
    
    def backtrack(current, open_count, close_count):
        # Base case: if we have used n pairs (2n characters), add to results
        if len(current) == 2 * n:
            results.append(current)
            return
        
        # Try adding '(' if we haven't reached the maximum number of open parentheses yet
        if open_count < n:
            backtrack(current + '(', open_count + 1, close_count)
        
        # Try adding ')' if it won't make the string unbalanced (more closes than opens)
        if close_count < open_count:
            backtrack(current + ')', open_count, close_count + 1)
    
    backtrack('', 0, 0)
    return results

def main():
    # Read exactly one JSON value from stdin
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        sys.exit(1)
    
    # Validate input type and value
    if not isinstance(input_data, int):
        print(json.dumps({"error": "Input must be an integer"}), file=sys.stderr)
        sys.exit(1)
    
    n = input_data
    
    # Ensure n is non-negative as per contract (n>=0)
    if n < 0:
        print(json.dumps({"error": "n must be >= 0"}), file=sys.stderr)
        sys.exit(1)
    
    # Generate balanced parentheses strings
    result = generate_balanced_parentheses(n)
    
    # Print exactly one JSON value: a list of strings
    print(json.dumps(result))

if __name__ == "__main__":
    main()