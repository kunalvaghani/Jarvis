import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list):
        return
    
    seen = set()
    result = []
    
    for item in input_data:
        if isinstance(item, int):
            if item not in seen:
                seen.add(item)
                result.append(item)
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()