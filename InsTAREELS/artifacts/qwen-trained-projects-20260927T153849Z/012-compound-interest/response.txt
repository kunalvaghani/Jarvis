import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 3:
            print(json.dumps(None), file=sys.stderr)
            return
        
        principal = input_data[0]
        annual_rate = input_data[1]
        years = input_data[2]
        
        if not (isinstance(principal, (int, float)) and isinstance(annual_rate, (int, float)) and isinstance(years, (int, float))):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if principal <= 0 or annual_rate <= 0 or years <= 0:
            print(json.dumps(None), file=sys.stderr)
            return
        
        interest_rate = (annual_rate / 100) / 12
        
        final_balance = principal * (1 + interest_rate) ** years
        result = round(final_balance, 2)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()