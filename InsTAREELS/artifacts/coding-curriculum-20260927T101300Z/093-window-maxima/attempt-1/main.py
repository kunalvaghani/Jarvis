import json
import sys

def sliding_window_maxima(nums: list[int], k: int) -> list[int]:
    """
    Compute the maximum of each complete sliding window of size k.
    Only windows that fit entirely within the input are considered.
    """
    if not nums or k <= 0:
        return []

    n = len(nums)
    result = []

    # Number of complete windows: (n - k + 1) if n >= k, else 0
    num_windows = max(0, n - k + 1)

    for i in range(num_windows):
        window_start = i
        window_end = i + k
        window = nums[window_start:window_end]
        result.append(max(window))

    return result


def main():
    # Read exactly one JSON value from stdin
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            print("[]", file=sys.stderr)
            return
        
        data = json.loads(input_data)
        
        # Validate input shape: must be a list of two elements [nums, k]
        if not isinstance(data, list) or len(data) != 2:
            print("[]", file=sys.stderr)
            return
        
        nums, k = data
        
        # Validate types
        if not isinstance(nums, list):
            print("[]", file=sys.stderr)
            return
        
        if not isinstance(k, int):
            print("[]", file=sys.stderr)
            return
        
        # Compute result
        result = sliding_window_maxima(nums, k)
        
        # Print exactly one JSON value (list of integers)
        print(json.dumps(result))
        
    except json.JSONDecodeError:
        print("[]", file=sys.stderr)
    except Exception:
        print("[]", file=sys.stderr)


if __name__ == "__main__":
    main()