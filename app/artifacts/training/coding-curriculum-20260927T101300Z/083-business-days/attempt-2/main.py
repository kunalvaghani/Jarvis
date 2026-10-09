import json
import sys
from datetime import date, timedelta

def main():
    try:
        input_data = json.load(sys.stdin)
        
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps({"error": "Input must be a list of two ISO date strings."}), file=sys.stderr)
            sys.exit(1)
        
        start_str = input_data[0]
        end_str = input_data[1]
        
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        except ValueError as e:
            print(json.dumps({"error": f"Invalid date format: {e}"}), file=sys.stderr)
            sys.exit(1)
        
        if start_date > end_date:
            print(json.dumps({"error": "Start date must be <= End date."}), file=sys.stderr)
            sys.exit(1)
        
        weekdays = []
        current = start_date
        while current < end_date:
            weekday_name = current.strftime("%A")
            if weekday_name in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
                weekdays.append(weekday_name)
            current += timedelta(days=1)
        
        print(json.dumps({"weekdays": weekdays}))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()