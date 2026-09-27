import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps([], separators=(',', ':')), file=sys.stderr)
            return
        sorted_data = sorted(input_data)
        print(json.dumps(sorted_data, separators=(',', ':')))  
    except Exception as e:
        print(json.dumps([], separators=(',', ':')), file=sys.stderr)

if __name__ == "__main__":
    main()