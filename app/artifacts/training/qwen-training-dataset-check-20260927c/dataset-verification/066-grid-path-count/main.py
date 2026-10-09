import json
import sys

def count_paths(rows: int, cols: int) -> int:
    """
    Count the number of paths from top-left to bottom-right in a grid,
    moving only right or down.
    Formula: C(n + m - 2, n - 1)
    """
    if rows <= 0 or cols <= 0:
        return 0
    
    n = rows - 1
    m = cols - 1
    total_steps = n + m
    steps_right = n
    
    # Calculate C(total_steps, steps_right)
    if steps_right < 0 or steps_right > total_steps:
        return 0
    
    result = 1
    for i in range(steps_right):
        result = result * (total_steps - i) // (i + 1)
    
    return result

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(None))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list) or len(data) != 2:
            print(json.dumps(None))
            return
        
        rows, cols = data[0], data[1]
        
        result = count_paths(rows, cols)
        print(json.dumps(result))
    except Exception:
        print(json.dumps(None))

if __name__ == "__main__":
    main()