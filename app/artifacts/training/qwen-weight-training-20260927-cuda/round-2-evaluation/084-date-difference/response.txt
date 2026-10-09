import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        start_date_str, end_date_str = input_data
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        
        if start_date > end_date:
            print(json.dumps(None), file=sys.stderr)
            return
        
        delta = end_date - start_date
        return json.dumps(delta.days)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()