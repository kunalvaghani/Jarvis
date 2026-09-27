import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, list):
            print(json.dumps(-1))
            return
        start_date = data[0]
        end_date = data[1]
        if not isinstance(start_date, str) or not isinstance(end_date, str):
            print(json.dumps(-1))
            return
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        if start_date > end_date:
            print(json.dumps(-1))
            return
        days = (end_date - start_date).days + 1
        print(json.dumps(days))
    except ValueError:
        print(json.dumps(-1))

if __name__ == "__main__":
    main()