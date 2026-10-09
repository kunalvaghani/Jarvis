import sys
import json

def find_second_largest_distinct(nums):
    unique_nums = set(nums)
    if len(unique_nums) < 2:
        return None
    sorted_unique_nums = sorted(unique_nums)
    return sorted_unique_nums[-2]

try:
    input_data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(1)

result = find_second_largest_distinct(input_data)
print(json.dumps(result))
