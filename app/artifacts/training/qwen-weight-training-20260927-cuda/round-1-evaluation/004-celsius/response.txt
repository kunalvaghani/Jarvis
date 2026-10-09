import json
import sys

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            print(json.dumps({"error": "Input is not a dictionary"}), file=sys.stderr)
            return
        celsius = data.get("celsius", 0)
        if not isinstance(celsius, (int, float)):
            print(json.dumps({"error": "Invalid input type"}), file=sys.stderr)
            return
        fahrenheit = (celsius * 9/5) + 32
        print(json.dumps(fahrenheit))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()