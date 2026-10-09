import sys
import json
import datetime

def is_weekday(date_str):
    try:
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date.weekday() < 5
    except ValueError:
        return False

def is_holiday(date_str):
    try:
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date.weekday() == 5
    except ValueError:
        return False

def count_weekdays(start_date, end_date):
    weekdays = []
    for date in range(int(start_date), int(end_date) + 1):
        if is_weekday(str(date)):
            weekdays.append(date)
    return len(weekdays)

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps(None))
            return
        
        start_date = data[0]
        end_date = data[1]
        
        if not (isinstance(start_date, str) and isinstance(end_date, str)):
            print(json.dumps(None))
            return
        
        result = count_weekdays(start_date, end_date)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None))

if __name__ == "__main__":
    main()