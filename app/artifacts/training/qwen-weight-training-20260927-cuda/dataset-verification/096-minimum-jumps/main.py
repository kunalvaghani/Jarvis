import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(-1), file=sys.stderr)
        return

    if not isinstance(input_data, list):
        print(json.dumps(-1), file=sys.stderr)
        return

    n = len(input_data)
    if n == 0:
        print(json.dumps(0))
        return

    if n == 1:
        print(json.dumps(0))
        return

    if input_data[0] < 0 or input_data[-1] < 0:
        print(json.dumps(-1), file=sys.stderr)
        return

    jumps = [float('inf')] * n
    jumps[0] = 0

    for i in range(n):
        if jumps[i] == float('inf'):
            continue
        capacity = input_data[i]
        if capacity < 0:
            continue
        for j in range(i + 1, min(i + capacity + 1, n)):
            if jumps[j] > jumps[i] + 1:
                jumps[j] = jumps[i] + 1

    if jumps[-1] == float('inf'):
        print(json.dumps(-1))
    else:
        print(json.dumps(jumps[-1]))

if __name__ == "__main__":
    main()