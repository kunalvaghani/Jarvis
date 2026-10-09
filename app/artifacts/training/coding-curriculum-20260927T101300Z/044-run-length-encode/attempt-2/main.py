import json
import sys

def run_length_encode(data):
    if not data:
        return []
    
    result = []
    current_char = data[0]
    count = 1
    
    for i in range(1, len(data)):
        if data[i] == current_char:
            count += 1
        else:
            result.append([current_char, count])
            current_char = data[i]
            count = 1
    
    result.append([current_char, count])
    return result

def main():
    try:
        input_data = json.load(sys.stdin)
        if isinstance(input_data, list):
            output = run_length_encode(input_data)
            print(json.dumps(output))
        else:
            print(json.dumps([]))
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")

if __name__ == "__main__":
    main()