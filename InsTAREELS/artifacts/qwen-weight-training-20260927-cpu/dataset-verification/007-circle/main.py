import sys
import math
import json

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(0.0))
            return
        
        radius = float(input_data)
        area = math.pi * (radius ** 2)
        print(json.dumps(area))
    except ValueError:
        print(json.dumps(0.0))

if __name__ == "__main__":
    main()