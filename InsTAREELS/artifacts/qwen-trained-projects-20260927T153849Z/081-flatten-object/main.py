import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, dict):
        return
    
    result = {}
    for key, value in input_data.items():
        if isinstance(value, (list, tuple)):
            result[key] = list(value)
        elif isinstance(value, dict):
            result[key] = main(value)
        else:
            result[key] = value
    return json.dumps(result)

if __name__ == "__main__":
    main()