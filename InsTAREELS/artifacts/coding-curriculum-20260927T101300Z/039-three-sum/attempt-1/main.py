import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return
    
    if not isinstance(input_data, list):
        print(json.dumps({"error": "Input must be a list"}), file=sys.stderr)
        return
    
    n = len(input_data)
    if n < 3:
        print(json.dumps([]))
        return
    
    result = []
    seen = set()
    
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if input_data[i] + input_data[j] + input_data[k] == 0:
                    triple = tuple(sorted([input_data[i], input_data[j], input_data[k]]))
                    if triple not in seen:
                        seen.add(triple)
                        result.append(list(triple))
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()