import sys
import bisect
import math

def max_area(heights):
    if not heights:
        return 0
    
    left = 0
    right = len(heights) - 1
    max_area = 0
    
    while left < right:
        h = min(heights[left], heights[right])
        width = right - left
        area = h * width
        
        if area > max_area:
            max_area = area
        
        if heights[left] < heights[right]:
            left += 1
        else:
            right -= 1
    
    return max_area

def histogram_area(heights):
    if not heights:
        return 0
    
    max_area = 0
    current_height = heights[0]
    
    for height in heights:
        if height > current_height:
            current_height = height
            max_area = max(max_area, (current_height * (len(heights) - i)))
        else:
            current_height *= (len(heights) - i)
    
    return max_area

def main():
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print(json.dumps(0))
            return
        
        data = json.loads(input_data)
        
        if not isinstance(data, list):
            print(json.dumps(0))
            return
        
        if not data:
            print(json.dumps(0))
            return
        
        result = max_area(data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(0))

if __name__ == "__main__":
    main()