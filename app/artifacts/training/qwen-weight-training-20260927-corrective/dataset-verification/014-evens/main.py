import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list):
        return
    
    result = []
    for item in input_data:
        if isinstance(item, int) and item % 2 == 0:
            result.append(item)
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()