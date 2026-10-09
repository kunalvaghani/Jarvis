import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps([]), file=sys.stderr)
            return
        
        result = []
        cumulative_sum = 0
        for num in input_data:
            if isinstance(num, (int, float)):
                cumulative_sum += num
                result.append(cumulative_sum)
            else:
                print(json.dumps([]), file=sys.stderr)
                return
        
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps([]), file=sys.stderr)
    except Exception:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()