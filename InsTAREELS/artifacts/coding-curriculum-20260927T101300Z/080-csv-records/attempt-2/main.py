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
                    # Handle CSV-like strings by parsing them as DictReader output
                    # The string represents a single row with headerless data or quoted fields
                    try:
                        # Try to parse the string as a simple key-value pair like "a,b" -> {"a": "b"}
                        # Or handle quoted fields like "\"x,y\",z" -> {"a": "x,y", "b": "z"}
                        # Since we don't have headers in the string itself, we assume a fixed structure
                        # Based on examples: "a,b" means key "a" has value "b"
                        # But looking at example 1: input "a,b\n1,2\n" -> [{"a": "1", "b": "2"}]
                        # This suggests the string is actually CSV content where the first line is headers
                        # However, the input is passed as a JSON list of strings or objects
                        
                        # Re-reading the contract: "CSV text with header to list of string-valued record objects"
                        # The examples show input as raw CSV text inside JSON strings
                        # Example 1: input "a,b\n1,2\n" is a single string in the list
                        # We need to parse this CSV string into records
                        
                        # Parse the CSV string
                        import io
                        csv_reader = DictReader(io.StringIO(item))
                        for row in csv_reader:
                            # Convert all values to strings (DictReader already does this, but ensure)
                            record = {k: str(v) for k, v in row.items()}
                            records.append(record)
                    except Exception:
                        # Fallback if CSV parsing fails
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