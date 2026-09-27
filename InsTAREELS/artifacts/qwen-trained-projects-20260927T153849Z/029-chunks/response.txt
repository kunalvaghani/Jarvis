import json
import sys

def process_chunk(chunk):
    if not chunk:
        return []
    result = []
    for i in range(0, len(chunk), chunksize):
        result.append(chunk[i:i+chunksize])
    return result

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list) or len(input_data) != 2:
            print(json.dumps(None), file=sys.stderr)
            return
        
        x, chunksize = input_data
        if not (isinstance(x, list) and isinstance(chunksize, int)):
            print(json.dumps(None), file=sys.stderr)
            return
        
        if not (isinstance(x[0], list) and all(isinstance(i, list) for i in x[0])):
            print(json.dumps(None), file=sys.stderr)
            return
        
        result = process_chunk(x[0])
        if not result:
            print(json.dumps(None), file=sys.stderr)
            return
        
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(None), file=sys.stderr)

if __name__ == "__main__":
    main()