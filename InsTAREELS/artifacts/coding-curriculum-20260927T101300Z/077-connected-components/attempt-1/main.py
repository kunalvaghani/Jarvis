import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(1)

    if not isinstance(input_data, dict):
        sys.exit(1)

    adj_list = {}
    for key in input_data:
        if not isinstance(key, str):
            continue
        neighbors = input_data[key]
        if not isinstance(neighbors, list):
            continue
        adj_list[key] = sorted(set(neighbors))

    components = []
    visited = set()

    for node in adj_list:
        if node not in visited:
            component = []
            stack = [node]
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                for neighbor in adj_list.get(current, []):
                    if neighbor not in visited:
                        stack.append(neighbor)
            components.append(sorted(component))

    components.sort(key=len)
    print(json.dumps(components))

if __name__ == "__main__":
    main()