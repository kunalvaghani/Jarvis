import sys
import json

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, dict):
            print(json.dumps({"error": "Input must be a JSON object"}), file=sys.stderr)
            return
        
        kg = input_data.get("kg")
        m = input_data.get("m")
        
        if kg is None or m is None:
            print(json.dumps({"error": "Missing 'kg' or 'm' field"}), file=sys.stderr)
            return
        
        if not isinstance(kg, (int, float)) or not isinstance(m, (int, float)):
            print(json.dumps({"error": "Values must be numbers"}), file=sys.stderr)
            return
        
        bmi = kg / ((m ** 2) * 1000)
        result = {"bmi": round(bmi, 4)}
        print(json.dumps(result))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()