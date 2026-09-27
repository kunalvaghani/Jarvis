import json
import sys
from csv import DictReader

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return
        
        parsed_input = json.loads(input_data)
        
        if isinstance(parsed_input, list):
            records = []
            for item in parsed_input:
                if isinstance(item, dict):
                    records.append(item)
                elif isinstance(item, str):
                    records.append({"value": item})
                else:
                    records.append({"value": str(item)})
            
            print(json.dumps(records))
        else:
            print(json.dumps([parsed_input]))
    except json.JSONDecodeError:
        sys.stderr.write("Error: Invalid JSON input\n")
        sys.exit(1)

if __name__ == "__main__":
    main()