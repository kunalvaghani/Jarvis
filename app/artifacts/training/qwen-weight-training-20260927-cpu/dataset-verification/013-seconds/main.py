import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, (int, float)):
        return
    
    seconds = int(input_data)
    
    if seconds < 0:
        return
    
    hours = seconds // 3600
    remaining_seconds = seconds % 3600
    minutes = remaining_seconds // 60
    final_seconds = remaining_seconds % 60
    
    result = [hours, minutes, final_seconds]
    print(json.dumps(result))

if __name__ == "__main__":
    main()