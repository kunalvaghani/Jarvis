import json
import sys

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list) or len(input_data) != 2:
        return
    
    graph, start_node = input_data
    
    if not isinstance(graph, dict) or not isinstance(start_node, str):
        return
    
    distances = {}
    queue = [start_node]
    distances[start_node] = 0
    visited = {start_node}
    
    while queue:
        current = queue.pop(0)
        if current in graph:
            for neighbor, weight in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    distances[neighbor] = distances[current] + weight
                    queue.append(neighbor)
    
    print(json.dumps(distances))

if __name__ == "__main__":
    main()