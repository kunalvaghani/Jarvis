import sys
import json


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, list) or len(input_data) != 2:
        return
    
    graph, start = input_data
    
    if not isinstance(graph, dict) or not isinstance(start, str):
        return
    
    if start not in graph:
        return
    
    result = []
    visited = set()
    
    def dfs(node):
        if node in visited:
            return
        visited.add(node)
        result.append(node)
        for neighbor in graph[node]:
            dfs(neighbor)
    
    dfs(start)
    print(json.dumps(result))


if __name__ == "__main__":
    main()