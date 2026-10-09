import json
import sys

def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps(0))
            return
        
        parsed = json.loads(input_data)
        
        if isinstance(parsed, list):
            words = []
            for item in parsed:
                if isinstance(item, str):
                    words.extend(item.split())
                elif isinstance(item, int):
                    words.append(str(item))
                else:
                    words.append(str(item))
        elif isinstance(parsed, dict):
            for value in parsed.values():
                if isinstance(value, str):
                    words.extend(value.split())
                elif isinstance(value, int):
                    words.append(str(value))
                else:
                    words.append(str(value))
        else:
            words = []
        
        print(json.dumps(len(words)))
    except json.JSONDecodeError:
        print(json.dumps(0))

if __name__ == "__main__":
    main()