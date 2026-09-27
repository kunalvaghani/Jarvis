import sys
import json
import collections

def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    
    if not isinstance(input_data, dict):
        return
    
    graph = collections.defaultdict(list)
    for node, neighbors in input_data.items():
        for neighbor in neighbors:
            graph[neighbor].append(node)
    
    components = []
    visited = set()
    component = []
    
    def dfs(node):
        if node in visited:
            return
        visited.add(node)
        component.append(node)
        for neighbor in graph[node]:
            dfs(neighbor)
    
    for node in graph:
        if node not in visited:
            dfs(node)
        components.append(component)
    
    result = [json.dumps(x) for x in components]
    print(json.dumps(result))

if __name__ == "__main__":
    main()