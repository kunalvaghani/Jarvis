import sys
import heapq
import json

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list):
            print(json.dumps(None))
            return
        
        unique_values = sorted(set(data))
        
        if len(unique_values) < 2:
            print(json.dumps(None))
            return
        
        return json.dumps(unique_values[-2])
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()