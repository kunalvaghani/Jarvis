import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        data, window_size = input_data
        
        if not isinstance(data, list) or not isinstance(window_size, int):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if not (0 <= window_size <= len(data)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        result = []
        for i in range(len(data) - window_size + 1):
            window = data[i:i+window_size]
            mean = sum(window) / window_size
            result.append(mean)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()