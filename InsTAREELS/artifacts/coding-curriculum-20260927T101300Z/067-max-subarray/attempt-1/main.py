import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(json.dumps(None), file=sys.stderr)
            return
        
        max_sum = float('-inf')
        current_sum = 0
        found = False
        
        for num in data:
            if not isinstance(num, (int, float)):
                continue
            current_sum += num
            if current_sum > max_sum:
                max_sum = current_sum
                found = True
        
        if not found:
            print(json.dumps(None), file=sys.stderr)
            return
        
        print(json.dumps(max_sum))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()