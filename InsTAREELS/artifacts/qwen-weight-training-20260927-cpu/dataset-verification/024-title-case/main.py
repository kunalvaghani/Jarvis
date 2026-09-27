import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if isinstance(input_data, list):
            result = [str(item).title() for item in input_data]
        else:
            result = str(input_data).title()
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()