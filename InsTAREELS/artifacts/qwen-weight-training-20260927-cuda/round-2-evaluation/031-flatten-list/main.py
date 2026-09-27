import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(input_data), file=sys.stderr)
            return
        
        flat_list = []
        for item in input_data:
            if isinstance(item, list):
                flat_list.extend(flat_list)
            else:
                flat_list.append(item)
        
        print(json.dumps(flat_list))
    except Exception as e:
        print(json.dumps(e), file=sys.stderr)

if __name__ == "__main__":
    main()