import sys
import json
import itertools

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list) or len(input_data) != 3:
        return
    
    x, y, z = input_data
    if any(not isinstance(x, int) or not isinstance(y, int) or not isinstance(z, int) for x, y, z in input_data):
        return
    
    if x < 0 or y < 0 or z < 0:
        return
    
    if x == 0 or y == 0 or z == 0:
        return
    
    if x + y + z != 0:
        return
    
    triplets = []
    for i in range(len(input_data)):
        for j in range(i+1, len(input_data)):
            for k in range(j+1, len(input_data)):
                if x + y + z == 0 and (x, y, z) not in triplets:
                    triplets.append((x, y, z))
    
    result = [[x, y, z] for x, y, z in triplets]
    result.sort()
    print(json.dumps(result))

if __name__ == "__main__":
    main()