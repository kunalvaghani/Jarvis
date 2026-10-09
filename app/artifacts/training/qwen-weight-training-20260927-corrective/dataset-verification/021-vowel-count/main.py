import json
import sys

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps(0))
            return
        
        parsed = json.loads(input_data)
        if not isinstance(parsed, (str, int, float, list, dict)):
            print(json.dumps(0))
            return
        
        text = str(parsed)
        vowels = set('aeiouAEIOU')
        count = sum(1 for char in text if char in vowels)
        
        print(json.dumps(count))
    except Exception:
        print(json.dumps(0))

if __name__ == "__main__":
    main()