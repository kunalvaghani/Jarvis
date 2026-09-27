import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 3:
            print(json.dumps(None), file=sys.stderr)
            return
        
        principal = input_data[0]
        annual_percent = input_data[1]
        years = input_data[2]
        
        if not (isinstance(principal, (int, float)) and isinstance(annual_percent, (int, float)) and isinstance(years, (int, float))):
            print(json.dumps(None), file=sys.stderr)
            return
        
        interest = principal * (annual_percent / 100) * years
        result = round(interest, 2)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()