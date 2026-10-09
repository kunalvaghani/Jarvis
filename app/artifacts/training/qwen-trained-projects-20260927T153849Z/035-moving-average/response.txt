import sys
import json

def mean(lst):
    return sum(lst) / len(lst)

def sliding_window_mean(data, window_size):
    result = []
    for i in range(len(data)):
        if i >= window_size:
            result.append(mean(data[i-window_size:i+1]))
    return result

try:
    input_data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(1)

result = sliding_window_mean(input_data[0], input_data[1])
print(json.dumps(result))
