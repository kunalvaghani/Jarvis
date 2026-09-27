import json
import sys

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps([]), file=sys.stderr)
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list):
            print(json.dumps([]), file=sys.stderr)
            return
        
        result = []
        for item in data:
            if not isinstance(item, str):
                print(json.dumps([]), file=sys.stderr)
                return
            
            words = item.split()
            word_count = len(words)
            
            if not word_count:
                continue
            
            if word_count == 1:
                result.append([word, 1])
            else:
                result.append([word, word_count])
        
        result.sort(key=lambda x: (-x[1], x[0]))
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps([]), file=sys.stderr)

if __name__ == "__main__":
    main()