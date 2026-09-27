import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(1)

    if not isinstance(input_data, list):
        sys.exit(1)

    unique_elements = sorted(set(input_data))
    permutations = []
    
    def generate_permutations(current, remaining):
        if len(remaining) == 0:
            permutations.append(current[:])
            return
        for i in range(len(unique_elements)):
            val = unique_elements[i]
            new_remaining = remaining.copy()
            new_remaining.pop(i)
            generate_permutations(current + [val], new_remaining)
    
    generate_permutations([], list(unique_elements))
    permutations.sort()

    print(json.dumps(permutations))

if __name__ == "__main__":
    main()