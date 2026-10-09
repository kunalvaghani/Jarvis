import sys

def parse_json(input_str):
    try:
        return json.loads(input_str)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON input")

def generate_parentheses(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    
    def backtrack(path, remaining):
        if not remaining:
            yield path[:]
        
        for i in range(len(remaining)):
            if remaining[i] == '(':
                yield from backtrack(path + [remaining[i]], remaining[:i] + remaining[i+1:])
            elif remaining[i] == ')':
                yield from backtrack(path, remaining[:i] + remaining[i+1:])
    
    return list(backtrack([], list(range(n))))

def main():
    input_str = sys.stdin.read()
    n = int(input_str.strip())
    
    try:
        result = generate_parentheses(n)
        print(json.dumps(result))
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
