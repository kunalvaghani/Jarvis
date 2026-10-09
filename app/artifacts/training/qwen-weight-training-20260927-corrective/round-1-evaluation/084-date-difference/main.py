import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        date1, date2 = input_data
        if not (isinstance(date1, str) and isinstance(date2, str)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        try:
            start_date = datetime.datetime.strptime(date1, "%Y-%m-%d")
            end_date = datetime.datetime.strptime(date2, "%Y-%m-%d")
        except ValueError:
            print(json.dumps(None), file=sys.stderr)
            return
        
        if start_date > end_date:
            print(json.dumps(None), file=sys.stderr)
            return
        
        delta = end_date - start_date
        return json.dumps(delta.days)
    except Exception:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()