import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        
        if not isinstance(data, list):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if len(data) == 0:
            print(json.dumps(None), file=sys.stderr)
            return
        
        max_sum = data[0]
        current_sum = data[0]
        
        for num in data[1:]:
            if not isinstance(num, (int, float)):
                continue
            current_sum += num
            if current_sum > max_sum:
                max_sum = current_sum
        
        print(json.dumps(max_sum))
    except json.JSONDecodeError:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()