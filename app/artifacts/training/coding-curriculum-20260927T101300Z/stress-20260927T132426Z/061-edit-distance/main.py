import json
import sys

def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps({"error": "Input must be a list of exactly two strings."}), file=sys.stderr)
            sys.exit(1)
        
        s1, s2 = input_data
        if not isinstance(s1, str) or not isinstance(s2, str):
            print(json.dumps({"error": "Both elements in the input list must be strings."}), file=sys.stderr)
            sys.exit(1)
        
        distance = levenshtein_distance(s1, s2)
        print(json.dumps(distance))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()