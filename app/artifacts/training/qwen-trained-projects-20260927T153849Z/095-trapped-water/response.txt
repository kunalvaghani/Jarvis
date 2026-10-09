import sys
import math

def trap(heights):
    if not heights:
        return 0
    
    left = 0
    right = len(heights) - 1
    max_left = max_right = 0
    
    result = 0
    
    while left < right:
        if heights[left] <= heights[right]:
            max_left = max(max_left, heights[left])
            result += (right - left) * (max_left - heights[left])
            left += 1
        else:
            max_right = max(max_right, heights[right])
            result += (right - left) * (max_right - heights[right])
            right -= 1
    
    return result

if __name__ == "__main__":
    import sys
    import json
    x = json.load(sys.stdin)
    result = trap(x)
    print(json.dumps(result))
