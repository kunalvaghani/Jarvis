import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(None))
        return

    if not isinstance(input_data, list) or len(input_data) != 3:
        print(json.dumps(None))
        return

    graph, start, target = input_data

    if not isinstance(graph, dict) or not isinstance(start, str) or not isinstance(target, str):
        print(json.dumps(None))
        return

    if start == target:
        print(json.dumps(0))
        return

    visited = set()
    queue = [(start, 0)]

    while queue:
        node, dist = queue.pop(0)

        if node in visited:
            continue

        visited.add(node)

        if node == target:
            print(json.dumps(dist))
            return

        if node not in graph:
            continue

        for neighbor in graph[node]:
            queue.append((neighbor, dist + 1))

    print(json.dumps(-1))

if __name__ == "__main__":
    main()