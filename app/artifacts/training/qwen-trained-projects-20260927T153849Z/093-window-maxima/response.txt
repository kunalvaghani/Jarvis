import sys
import json

def maxSlidingWindow(nums, k):
    result = []
    if not nums or k <= 0:
        return result
    
    queue = []
    for i in range(len(nums)):
        while queue and nums[queue[-1]] < nums[i]:
            queue.pop()
        queue.append(i)
        
        if i >= k:
            result.append(nums[queue[0]])
            if queue[0] == 0:
                queue.pop(0)
    
    return result

x = json.load(sys.stdin)
result = maxSlidingWindow(x[0], x[1])
print(json.dumps(result))
