import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(1)

    if not isinstance(input_data, list):
        sys.exit(1)

    n = len(input_data)
    if n == 0:
        print(0)
        return

    heights = input_data
    left_max = [0] * n
    right_max = [0] * n

    left_max[0] = heights[0]
    for i in range(1, n):
        left_max[i] = max(left_max[i - 1], heights[i])

    right_max[n - 1] = heights[n - 1]
    for i in range(n - 2, -1, -1):
        right_max[i] = max(right_max[i + 1], heights[i])

    trapped_water = 0
    for i in range(n):
        water_level = min(left_max[i], right_max[i])
        trapped_water += max(0, water_level - heights[i])

    print(trapped_water)

if __name__ == "__main__":
    main()