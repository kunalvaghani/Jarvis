import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        date1 = input_data[0]
        date2 = input_data[1]
        
        if not isinstance(date1, str) or not isinstance(date2, str):
            print(json.dumps(None), file=sys.stderr)
            return
        
        try:
            parsed_date1 = datetime.strptime(date1, "%Y-%m-%d")
            parsed_date2 = datetime.strptime(date2, "%Y-%m-%d")
        except ValueError:
            print(json.dumps(None), file=sys.stderr)
            return
        
        if parsed_date1 > parsed_date2:
            print(json.dumps(-1))
            return
        
        start_day = parsed_date1.replace(day=1)
        end_day = parsed_date2.replace(day=1)
        
        delta = end_day - start_day
        if delta.days == 0:
            print(json.dumps(0))
        else:
            print(json.dumps(delta.days))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()