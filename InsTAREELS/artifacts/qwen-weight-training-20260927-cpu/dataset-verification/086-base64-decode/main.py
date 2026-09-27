import json
import sys
import base64

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            return
        
        decoded_bytes = base64.b64decode(input_data)
        decoded_string = decoded_bytes.decode('utf-8')
        
        result = json.dumps(decoded_string)
        print(result)
    except Exception as e:
        pass

if __name__ == "__main__":
    main()