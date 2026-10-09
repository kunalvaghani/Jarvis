import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(1)
            return
        result = 1
        for item in data:
            if isinstance(item, (int, float)):
                result *= item
            elif isinstance(item, list):
                result *= multiply_list(item)
        print(result)
    except json.JSONDecodeError:
        print(1)

def multiply_list(lst):
    if not lst:
        return 1
    result = 1
    for item in lst:
        if isinstance(item, (int, float)):
            result *= item
        elif isinstance(item, list):
            result *= multiply_list(item)
    return result

if __name__ == "__main__":
    main()