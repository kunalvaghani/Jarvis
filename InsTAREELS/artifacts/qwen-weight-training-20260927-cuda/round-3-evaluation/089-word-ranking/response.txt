import json
import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list):
            print(json.dumps([]))
            return
        
        result = []
        for item in data:
            if not isinstance(item, str):
                continue
            
            words = item.split()
            word_count = len(words)
            
            if word_count == 0:
                continue
            
            if word_count > 1:
                result.append((word, word_count))
        
        result.sort(key=lambda x: (-x[1], x[0].lower()))
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()