import json
import sys
import base64

def main():
    try:
        input_data = json.load(sys.stdin)
        if isinstance(input_data, str):
            encoded = base64.b64encode(input_data.encode('utf-8')).decode('ascii')
            print(encoded)
        else:
            print(json.dumps(None))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()