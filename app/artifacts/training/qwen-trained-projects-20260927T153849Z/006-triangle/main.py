import sys
import math

def calculate_triangle_area(base, height):
    return (base * height) / 2.0

try:
    input_data = sys.stdin.read()
    if not input_data.strip():
        print(json.dumps(None))
        sys.exit(0)
    
    data = json.loads(input_data)
    if not isinstance(data, list) or len(data) != 2:
        print(json.dumps(None))
        sys.exit(0)
    
    base = data[0]
    height = data[1]
    
    result = calculate_triangle_area(base, height)
    print(json.dumps(result))
except Exception as e:
    print(json.dumps(None), file=sys.stderr)
    sys.exit(1)
