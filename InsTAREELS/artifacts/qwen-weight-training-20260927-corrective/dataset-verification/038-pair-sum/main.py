import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps({"error": "Input must be a list with exactly two elements: [list_of_numbers, target]"}), file=sys.stderr)
            sys.exit(1)
        
        numbers = input_data[0]
        target = input_data[1]
        
        if not isinstance(numbers, list) or not all(isinstance(n, (int, float)) for n in numbers):
            print(json.dumps({"error": "First element must be a list of numbers"}), file=sys.stderr)
            sys.exit(1)
        
        if not isinstance(target, (int, float)):
            print(json.dumps({"error": "Second element must be a number"}), file=sys.stderr)
            sys.exit(1)
        
        result = []
        seen_pairs = set()
        n = len(numbers)
        
        for i in range(n):
            for j in range(i + 1, n):
                if numbers[i] + numbers[j] == target:
                    pair = (min(numbers[i], numbers[j]), max(numbers[i], numbers[j]))
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        result.append(list(pair))
        
        print(json.dumps(result))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()