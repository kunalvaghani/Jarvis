import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, int) or input_data <= 0:
        return
    
    divisors = []
    for i in range(1, input_data + 1):
        if input_data % i == 0:
            divisors.append(i)
    
    print(json.dumps(divisors))

if __name__ == "__main__":
    main()