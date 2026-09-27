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
        
        if not (isinstance(data[0], list) and len(data[0]) == 2 and isinstance(data[1], int)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        result = []
        
        for i in range(len(data[0])):
            left = i
            right = i + window_size - 1
            
            if left < 0 or right >= len(data[0]):
                continue
            
            current_sum = sum(data[0][left:right+1])
            result.append(current_sum / window_size)
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()