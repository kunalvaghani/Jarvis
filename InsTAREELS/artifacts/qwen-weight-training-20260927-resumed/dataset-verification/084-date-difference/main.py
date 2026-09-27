import json
import sys
from datetime import datetime

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        start_str, end_str = input_data
        try:
            start_date = datetime.fromisoformat(start_str)
            end_date = datetime.fromisoformat(end_str)
        except ValueError:
            print(json.dumps(None), file=sys.stderr)
            return
        delta = end_date - start_date
        days = delta.days
        print(json.dumps(days))
    except Exception:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()