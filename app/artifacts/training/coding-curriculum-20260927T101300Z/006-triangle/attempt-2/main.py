import sys
import json

def main():
    try:
        data = sys.stdin.read().strip()
        if not data:
            return
        
        values = [float(x) for x in data.split()]
        if len(values) != 2:
            return
        
        base, height = values
        area = 0.5 * base * height
        print(json.dumps(area))
    except (ValueError, IndexError):
        pass

if __name__ == "__main__":
    main()