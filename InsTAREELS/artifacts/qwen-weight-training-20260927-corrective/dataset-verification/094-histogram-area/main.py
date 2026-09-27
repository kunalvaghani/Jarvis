import json
import sys

def largest_rectangle_area(heights):
    stack = []
    max_area = 0
    for i in range(len(heights) + 1):
        h = heights[i] if i < len(heights) else 0
        while stack and h < heights[stack[-1]]:
            height = heights[stack.pop()]
            width = i if not stack else i - stack[-1] - 1
            max_area = max(max_area, height * width)
        stack.append(i)
    return max_area

def main():
    try:
        input_data = json.load(sys.stdin)
        if not isinstance(input_data, list):
            print(json.dumps(0), file=sys.stderr)
            sys.exit(1)
        result = largest_rectangle_area(input_data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps(0), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()